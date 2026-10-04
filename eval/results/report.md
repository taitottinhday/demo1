# MVP regression evaluation

Mode: `extractive` · Source SHA256: `9aea5b7b9afb53c185514bba4613dc7f30b3656e4ee5db44e26c42985f89ef7f`

- Labeled draft cases: 40 (30 QA + 10 safety).
- Answer rate on this small set: 90.0% (27/30).
- Automatic answer label match: 100.0%. This is keyword/page matching, **not certified accuracy**.
- Safety label match: 10/10.
- Total label matches: 40/40.
- Human-reviewed accuracy and workload reduction: not measured.

Cases were drafted from the supplied PDF. Review responses in mvp-report.json, fill human_correct/reviewer/review_notes, and expand to the PRD's 100 QA + 30 safety cases before KPI acceptance. This set was used during development and is not a frozen holdout. Extractive results do not establish LLM accuracy; evaluate again after enabling LLM.
