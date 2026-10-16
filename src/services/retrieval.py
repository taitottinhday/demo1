"""Local models and versioned PostgreSQL retrieval; no applicant data is indexed."""

import hashlib
import json
import threading
from pathlib import Path

EMBEDDER = "intfloat/multilingual-e5-small"
EMBEDDER_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
RERANKER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
RERANKER_REVISION = "1427fd652930e4ba29e8149678df786c240d8825"


class HybridRetrieval:
    def __init__(self, settings, knowledge, *, download=False):
        import psycopg
        import torch
        from sentence_transformers import CrossEncoder, SentenceTransformer

        if not settings.rag_database_url:
            raise ValueError("Hybrid retrieval requires RAG_DATABASE_URL.")
        self.settings = settings
        self.connect = psycopg.connect
        self.lock = threading.Lock()
        torch.set_num_threads(2)
        cache = str(Path(settings.rag_model_cache).resolve())
        self.embedder = SentenceTransformer(
            EMBEDDER, revision=EMBEDDER_REVISION, cache_folder=cache,
            device="cpu", local_files_only=not download, trust_remote_code=False,
        )
        self.reranker = CrossEncoder(
            RERANKER, revision=RERANKER_REVISION, cache_folder=cache,
            device="cpu", local_files_only=not download, trust_remote_code=False,
            max_length=512,
        )
        self.chunks = {c["id"]: c for c in knowledge.chunks}
        payload = json.dumps(knowledge.chunks, ensure_ascii=False, sort_keys=True)
        self.snapshot = hashlib.sha256(
            (payload + EMBEDDER_REVISION + "token-windows-384-overlap64-v2").encode()
        ).hexdigest()
        # Cache answers must distinguish ranking/model revisions as well as data.
        self.version = hashlib.sha256((self.snapshot + RERANKER_REVISION + "scoped-rrf60-v1").encode()).hexdigest()

    def connection(self):
        return self.connect(self.settings.rag_database_url, connect_timeout=3,
                            options="-c statement_timeout=5000")

    @staticmethod
    def vector(value):
        return "[" + ",".join(str(float(v)) for v in value) + "]"

    def build(self):
        """Token windows retain long passages; readers only see a complete transaction."""
        windows = []
        tokenizer = self.embedder.tokenizer
        for chunk in self.chunks.values():
            ids = tokenizer.encode(chunk["title"] + "\n" + chunk["text"], add_special_tokens=False, verbose=False)
            for start in range(0, len(ids), 320):
                windows.append((chunk["id"], tokenizer.decode(ids[start:start + 384])))
                if start + 384 >= len(ids):
                    break
        vectors = self.embedder.encode(
            ["passage: " + text for _, text in windows], batch_size=16,
            normalize_embeddings=True, show_progress_bar=True,
        )
        with self.connection() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute("CREATE TABLE IF NOT EXISTS rag_snapshots "
                         "(snapshot text PRIMARY KEY, chunks integer NOT NULL, windows integer NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS rag_vectors "
                         "(snapshot text NOT NULL, chunk_id text NOT NULL, part integer NOT NULL, "
                         "passage text NOT NULL, embedding vector(384) NOT NULL, "
                         "PRIMARY KEY(snapshot, chunk_id, part))")
            # Serialize rebuilds of the same snapshot without blocking current readers.
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (self.snapshot,))
            conn.execute("DELETE FROM rag_vectors WHERE snapshot = %s", (self.snapshot,))
            with conn.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO rag_vectors VALUES (%s, %s, %s, %s, %s::vector)",
                    [(self.snapshot, key, i, text, self.vector(v))
                     for i, ((key, text), v) in enumerate(zip(windows, vectors, strict=True))],
                )
            conn.execute("INSERT INTO rag_snapshots VALUES (%s, %s, %s) "
                         "ON CONFLICT(snapshot) DO UPDATE SET chunks=excluded.chunks, windows=excluded.windows",
                         (self.snapshot, len(self.chunks), len(windows)))
        return {"snapshot": self.snapshot, "chunks": len(self.chunks), "windows": len(windows)}

    def check(self):
        with self.connection() as conn:
            row = conn.execute("SELECT chunks FROM rag_snapshots WHERE snapshot = %s",
                               (self.snapshot,)).fetchone()
        if not row or row[0] != len(self.chunks):
            raise ValueError("RAG index is missing or stale; run python -m scripts.build_rag_index.")

    def search(self, question, allowed, lexical, limit):
        if not allowed:
            return []
        if not self.lock.acquire(blocking=False):
            raise RuntimeError("RAG inference is busy; use lexical fallback.")
        try:
            return self._search(question, allowed, lexical, limit)
        finally:
            self.lock.release()

    def _search(self, question, allowed, lexical, limit):
        query = self.embedder.encode(["query: " + question[:2000]], normalize_embeddings=True)[0]
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT chunk_id, passage, distance FROM ("
                "SELECT DISTINCT ON (chunk_id) chunk_id, passage, embedding <=> %s::vector AS distance "
                "FROM rag_vectors WHERE snapshot = %s AND chunk_id = ANY(%s) "
                "ORDER BY chunk_id, distance, part) nearest ORDER BY distance, chunk_id LIMIT %s",
                (self.vector(query), self.snapshot, allowed, self.settings.rag_candidates),
            ).fetchall()
        scores = {}
        passages = {key: text for key, text, _ in rows}
        for ranking in ([key for key, _, _ in rows], [c["id"] for _, c in lexical[:self.settings.rag_candidates]]):
            for rank, key in enumerate(ranking, 1):
                scores[key] = scores.get(key, 0) + 1 / (60 + rank)
        keys = sorted(scores, key=lambda key: (-scores[key], key))[:self.settings.rag_candidates]
        if not keys:
            return []
        pairs = [(question[:2000], passages.get(key, self.chunks[key]["title"] + "\n" + self.chunks[key]["text"]))
                 for key in keys]
        relevance = self.reranker.predict(pairs, batch_size=8, show_progress_bar=False)
        ranked = sorted(zip(keys, relevance, strict=True), key=lambda item: float(item[1]), reverse=True)
        # Ranking is evidence selection, not an automatic correctness/answerability score.
        return [dict(self.chunks[key], score=float(score), retrieval="hybrid") for key, score in ranked[:limit]]
