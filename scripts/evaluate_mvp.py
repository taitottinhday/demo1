"""Deterministic regression eval; not a substitute for human admissions review.

python -m scripts.evaluate_mvp
python -m scripts.evaluate_mvp --mode llm  # makes real paid API calls when configured
"""

import argparse
import asyncio
import hashlib
import json
import statistics
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from src.config import get_settings
from src.services.admissions import Admissions
from src.services.knowledge import Knowledge, normalize
from src.services.store import Store


async def evaluate(mode, suite="mvp", max_cases=None, retrieval=None, case_ids=None, output_path=None):
    if mode == "llm" and (max_cases is None or not 1 <= max_cases <= 100):
        raise ValueError("Paid evaluation requires max_cases between 1 and 100")
    settings = get_settings().model_copy(update={"answer_mode": mode})
    if retrieval:
        settings = settings.model_copy(update={"retrieval_mode": retrieval})
    knowledge = Knowledge(settings.mvp_data_dir, settings)
    knowledge.ingest()
    if settings.retrieval_mode == "hybrid" and knowledge.manifest.get("retrieval") != "hybrid":
        raise RuntimeError("Hybrid evaluation requires a ready vector index and cached models.")
    root = Path("data/test-tmp")
    root.mkdir(parents=True, exist_ok=True)
    dataset_path = Path("eval/cases.json")
    if suite == "review":
        dataset_path = Path("eval/admissions_review.jsonl")
        cases = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        cases = [{**case, "expected_fact_sources": case["source_ids"]} for case in cases]
    elif suite == "golden":
        dataset_path = Path(settings.mvp_data_dir) / "evaluation/admissions_2026_golden.jsonl"
        cases = [json.loads(line) for line in (Path(settings.mvp_data_dir) / "evaluation/admissions_2026_golden.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        facts = {fact["id"]: fact for fact in json.loads((Path(settings.mvp_data_dir) / "normalized/admissions_facts_2026.json").read_text(encoding="utf-8"))["facts"]}
        cases = [{**case, "expected_kind": "fallback" if case["expected_behavior"].startswith("abstain_") else "answered",
                  "safety": case["expected_behavior"].startswith("abstain_"),
                  "expected_fact_sources": sorted({facts[key]["source_id"] for key in case["fact_ids"]})}
                 for case in cases]
    else:
        cases = json.loads(Path("eval/cases.json").read_text(encoding="utf-8"))
    if case_ids:
        unknown = set(case_ids) - {case["id"] for case in cases}
        if unknown:
            raise ValueError("Unknown case IDs: " + ", ".join(sorted(unknown)))
        cases = [case for case in cases if case["id"] in case_ids]
    if max_cases is not None:
        cases = cases[:max_cases]
    rows = []
    with tempfile.TemporaryDirectory(dir=root) as folder:
        service = Admissions(knowledge, Store(Path(folder) / "eval.db"), settings)
        for case in cases:
            started = time.perf_counter()
            diagnostics = {}
            answer = await service.answer(case["question"], case.get("program", ""), diagnostics=diagnostics)
            latency_ms = round(1000 * (time.perf_counter() - started))
            print(f"{case['id']}: {answer['kind']}", file=sys.stderr, flush=True)
            source_pages = {s["page"] for s in answer["sources"]}
            if suite in {"golden", "review"}:
                matched = answer["kind"] == case["expected_kind"] and set(case["expected_fact_sources"]).issubset(
                    {source["source_id"] for source in answer["sources"]})
                if suite == "review" and matched:
                    matched = all(any(source["source_id"] == e["source_id"] and (
                        e["page"] is None or (source["page"] is not None
                        and source["page"] <= e["end_page"] and (source["end_page"] or source["page"]) >= e["page"])
                    ) for source in answer["sources"]) for e in case["evidence"])
            else:
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
                    "tokens": answer.get("tokens", 0),
                    "answer_mode": answer.get("mode"),
                    "answer_reason": answer.get("reason"),
                    "latency_ms": latency_ms,
                    "generation_check": diagnostics.get("check"),
                    "human_correct": None,
                    "human_expected_kind": None,
                    "reviewer": None,
                    "review_notes": "",
                }
            )
    qa = [r for r in rows if not r.get("safety")]
    answered = [r for r in qa if r["actual_kind"] == "answered"]
    safety = [r for r in rows if r.get("safety")]
    latencies = [r["latency_ms"] for r in rows]
    summary = {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "llm_provider": settings.llm_provider if mode == "llm" else None,
        "llm_model": (settings.deepseek_model if settings.llm_provider == "deepseek" else settings.model_name)
        if mode == "llm" else None,
        "source_version": knowledge.manifest["version"],
        "case_count": len(rows),
        "qa_count": len(qa),
        "answered": len(answered),
        "answer_rate": round(100 * len(answered) / len(qa), 2) if qa else None,
        "automatic_label_match_on_answers": round(100 * sum(r["label_match"] for r in answered) / len(answered), 2)
        if answered
        else None,
        "accuracy_human": None,
        "safety_pass": sum(r["label_match"] for r in safety),
        "safety_count": len(safety),
        "label_match_total": sum(r["label_match"] for r in rows),
        "rows": rows,
        "suite": suite,
        "split": "review_draft" if suite == "review" else "development_not_holdout",
        "dataset_sha256": hashlib.sha256(dataset_path.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
        "data_release": knowledge.manifest.get("data_release"),
        "tokens": sum(row["tokens"] for row in rows),
        "token_usage_note": "Known provider usage; timeouts may be billed without returned usage.",
        "retrieval": knowledge.manifest.get("retrieval", "bm25"),
        "retrieval_version": knowledge.manifest["version"],
        "latency_p50_ms": statistics.median(latencies) if latencies else None,
        "latency_p95_ms": round(statistics.quantiles(latencies, n=100, method="inclusive")[94])
        if len(latencies) > 1 else (latencies[0] if latencies else None),
        "kpi_verified": False,
    }
    output = Path("eval/results")
    output.mkdir(parents=True, exist_ok=True)
    report_name = {"golden": "golden-report", "review": "review-report", "mvp": "mvp-report"}[suite]
    if settings.retrieval_mode == "hybrid":
        report_name += "-hybrid"
    if mode == "llm":
        report_name += "-llm"
    report_file = Path(output_path) if output_path else output / f"{report_name}.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    if suite in {"golden", "review"}:
        summary["automatic_behavior_source_match"] = summary.pop("automatic_label_match_on_answers")
        report_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: value for key, value in summary.items() if key != "rows"}, ensure_ascii=False, indent=2))
        return all(row["label_match"] for row in rows)
    report_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
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
    (output / ("report.md" if report_name == "mvp-report" else report_name + ".md")).write_text(report, encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return all(r["label_match"] for r in rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["extractive", "llm"], default="extractive")
    parser.add_argument("--suite", choices=["mvp", "golden", "review"], default="mvp")
    parser.add_argument("--retrieval", choices=["bm25", "hybrid"])
    parser.add_argument("--case-id", action="append", help="Evaluate only these canonical case IDs; repeatable")
    parser.add_argument("--output", type=Path, help="Save a separate report, preserving earlier runs and reviews")
    parser.add_argument("--max-calls", type=int, help="Explicit upper bound on evaluated cases for paid runs")
    args = parser.parse_args()
    if args.mode == "llm" and (args.max_calls is None or not 1 <= args.max_calls <= 100):
        parser.error("LLM evaluation requires --max-calls between 1 and 100; this makes paid usage explicit.")
    if args.max_calls is not None and args.max_calls < 1:
        parser.error("--max-calls must be positive")
    raise SystemExit(0 if asyncio.run(evaluate(args.mode, args.suite, args.max_calls, args.retrieval, args.case_id, args.output)) else 1)
