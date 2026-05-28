# Origin AI Lab

Origin AI Lab is an MVP scaffold for AI-assisted scientific data analysis and Origin/OriginPro figure automation.

The product direction is deliberately conservative: the AI should plan and explain, while deterministic tools ingest data, run analysis, validate results, and create reproducible artifacts. Origin automation sits behind a dedicated Windows connector so the rest of the system can run and test without a licensed Origin installation.

## Current Status

- Feasibility report: `docs/feasibility_report.md`
- Architecture route: `docs/architecture.md`
- Requirement intake design: `docs/requirement_intake_design.md`
- Design principles: `docs/design_principles.md`
- AI integration note: `docs/ai_integration.md`
- Evaluation report: `docs/evaluation_report.md`
- Roadmap: `docs/roadmap.md`
- MVP acceptance gates: `docs/mvp_acceptance.md`
- First workflow: CSV profile + XY regression + plot specification, with optional Origin export hook.
- First web UI: `web/index.html`, served by `src/origin_ai_lab/web_server.py`

## Quick Start

```powershell
python -m pip install -e .
python -m origin_ai_lab intake "帮我画散点图，加线性拟合，导出 png" --dataset examples\sample_xy.csv
origin-ai analyze examples/sample_xy.csv --out runs/demo --no-origin
python scripts\evaluate_intake_cases.py --planner rule
python scripts\qwen_smoke_test.py --model qwen3.7-max
$env:PYTHONPATH='src'; python -m origin_ai_lab.web_server
python -m unittest discover -s tests
python scripts\check_guardrails.py --policy .codex\harness-policy.json
```

If `origin-ai` is not on `PATH` after editable install, use the module entry point:

```powershell
python -m origin_ai_lab.cli analyze examples\sample_xy.csv --out runs/demo --no-origin
```

Then open:

```text
http://127.0.0.1:8765
```

In the web UI, use the "千问设置" panel to save a DashScope key locally. The key is encrypted with Windows DPAPI and is not stored in the repository.

For a real Origin smoke test on this machine, use the dedicated Origin environment:

```powershell
& "C:\Users\hp\Documents\New project\cad-origin-env\Scripts\python.exe" scripts\origin_smoke_test.py
```

## MVP Scope

1. Receive a natural-language plotting or analysis request.
2. Turn the request into intent, slots, assumptions, and clarification questions.
3. Ingest CSV/Excel-like tabular data.
4. Profile columns and infer candidate X/Y series.
5. Run deterministic analysis with explicit assumptions.
6. Validate numeric outputs and plot specifications.
7. Export artifacts locally.
8. Use Origin/OriginPro for final project and figure generation when available.

## Non-Goals For The First Milestone

- No autonomous rewriting of raw research data.
- No GUI screen-control fallback unless all proper APIs fail.
- No cloud upload of private datasets by default.
- No claim that AI-selected analysis methods are scientifically correct without validation.
