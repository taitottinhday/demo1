"""Run from the repository root: python -m scripts.ingest_sources."""

from src.config import get_settings
from src.services.knowledge import Knowledge

if __name__ == "__main__":
    knowledge = Knowledge(get_settings().mvp_data_dir)
    info = knowledge.ingest()
    print(f"PDF: {info['pages']} pages | Programs: {len(knowledge.programs)} | Chunks: {len(knowledge.chunks)}")
    print(f"SHA256: {info['version']}")
