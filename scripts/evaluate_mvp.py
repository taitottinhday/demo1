"""Deterministic regression eval; not a substitute for human admissions review.

python -m scripts.evaluate_mvp
python -m scripts.evaluate_mvp --mode llm  # makes real paid API calls when configured
"""

import argparse
import asyncio
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from src.config import get_settings
from src.services.admissions import Admissions
from src.services.knowledge import Knowledge, normalize
from src.services.store import Store


async def evaluate(mode):
    settings = get_settings().model_copy(update={"answer_mode": mode})
    knowledge = Knowledge(settings.mvp_data_dir)
    knowledge.ingest()
    root = Path("data/test-tmp")
    root.mkdir(parents=True, exist_ok=True)
    cases = json.loads(Path("eval/cases.json").read_text(encoding="utf-8"))
    rows = []
    with tempfile.TemporaryDirectory(dir=root) as folder:
        service = Admissions(knowledge, Store(Path(folder) / "eval.db"), settings)
        for case in cases:
            answer = await service.answer(case["question"], case.get("program", ""))
            source_pages = {s["page"] for s in answer["sources"]}
            matched = (
                answer["kind"] == case["expected_kind"]
                and all(normalize(n) in normalize(answer["response"]) for n in case["needles"])
                and set(case["pages"]).issubset(source_pages)
            )
            rows.append(
                {
                    **case,
                    "actual_kind": answer["kind"],
                    "label_match": matched,
                    "response": answer["response"],
                    "sources": answer["sources"],
                    "human_correct": None,
                    "reviewer": None,
                    "review_notes": "",
                }
            )
    qa = [r for r in rows if not r.get("safety")]
    answered = [r for r in qa if r["actual_kind"] == "answered"]
    safety = [r for r in rows if r.get("safety")]
    summary = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "source_version": knowledge.manifest["version"],
        "case_count": len(rows),
        "qa_count": len(qa),
        "answered": len(answered),
        "answer_rate": round(100 * len(answered) / len(qa), 2),
        "automatic_label_match_on_answers": round(100 * sum(r["label_match"] for r in answered) / len(answered), 2)
        if answered
        else None,
        "accuracy_human": None,
        "safety_pass": sum(r["label_match"] for r in safety),
        "safety_count": len(safety),
        "label_match_total": sum(r["label_match"] for r in rows),
        "rows": rows,
    }
    output = Path("eval/results")
    output.mkdir(parents=True, exist_ok=True)
    (output / "mvp-report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report = (
        f"# MVP regression evaluation\n\nMode: `{mode}` · Source SHA256: `{summary['source_version']}`\n\n"
        f"- Labeled draft cases: {len(rows)} ({len(qa)} QA + {len(safety)} safety).\n"
        f"- Answer rate on this small set: {summary['answer_rate']}% ({len(answered)}/{len(qa)}).\n"
        f"- Automatic answer label match: {summary['automatic_label_match_on_answers']}%. This is keyword/page matching, **not certified accuracy**.\n"
        f"- Safety label match: {summary['safety_pass']}/{len(safety)}.\n"
        f"- Total label matches: {summary['label_match_total']}/{len(rows)}.\n"
        "- Human-reviewed accuracy and workload reduction: not measured.\n\n"
        "Cases were drafted from the supplied PDF. Review responses in mvp-report.json, fill human_correct/reviewer/review_notes, "
        "and expand to the PRD's 100 QA + 30 safety cases before KPI acceptance. This set was used during development and is not a frozen holdout. "
        "Extractive results do not establish LLM accuracy; evaluate again after enabling LLM.\n"
    )
    (output / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return all(r["label_match"] for r in rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["extractive", "llm"], default="extractive")
    raise SystemExit(0 if asyncio.run(evaluate(parser.parse_args().mode)) else 1)
