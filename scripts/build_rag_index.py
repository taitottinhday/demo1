"""Build the public-source vector index explicitly, without calling a paid LLM."""

import json

from src.config import get_settings
from src.services.knowledge import Knowledge
from src.services.retrieval import HybridRetrieval


def main():
    settings = get_settings()
    print("Validating public-source snapshot...", flush=True)
    knowledge = Knowledge(settings.mvp_data_dir)
    knowledge.ingest()
    print("Loading pinned CPU models...", flush=True)
    retrieval = HybridRetrieval(settings, knowledge, download=True)
    print("Building vector snapshot...", flush=True)
    print(json.dumps(retrieval.build()))


if __name__ == "__main__":
    main()
