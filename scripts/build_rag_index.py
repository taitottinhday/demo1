"""Build the public-source vector index explicitly, without calling a paid LLM."""

import argparse
import json

from src.config import get_settings
from src.services.knowledge import Knowledge
from src.services.retrieval import HybridRetrieval


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--if-needed", action="store_true", help="Keep an already current vector snapshot")
    args = parser.parse_args()
    settings = get_settings()
    print("Validating public-source snapshot...", flush=True)
    knowledge = Knowledge(settings.mvp_data_dir)
    knowledge.ingest()
    print("Loading pinned CPU models...", flush=True)
    try:
        retrieval = HybridRetrieval(settings, knowledge, download=False)
    except OSError:
        retrieval = HybridRetrieval(settings, knowledge, download=True)
    if args.if_needed:
        from psycopg.errors import UndefinedTable

        try:
            retrieval.check()
        except (ValueError, UndefinedTable):
            pass  # A missing table/snapshot is expected on the first deployment.
        else:
            print(json.dumps({"snapshot": retrieval.snapshot, "status": "already_current"}), flush=True)
            return
    print("Building vector snapshot...", flush=True)
    print(json.dumps(retrieval.build()))


if __name__ == "__main__":
    main()
