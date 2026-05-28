# AGENTS.md

## Project Snapshot

- Purpose: AI-assisted scientific data analysis and Origin/OriginPro figure automation.
- Primary users: graduate students, lab engineers, research assistants, and PIs who repeat CSV/Excel/import-clean-fit-plot-report workflows.
- Current phase: feasibility validated, MVP scaffold in place.
- Important constraints: Origin automation is Windows-local and requires a licensed Origin/OriginPro installation. AI output must be treated as a plan to validate, not as scientific truth.

## Commands

- Install dev package: `python -m pip install -e .`
- Run CLI without Origin: `origin-ai analyze examples/sample_xy.csv --out runs/demo --no-origin`
- Run web UI: `$env:PYTHONPATH='src'; python -m origin_ai_lab.web_server`
- Run Origin smoke test: `& "C:\Users\hp\Documents\New project\cad-origin-env\Scripts\python.exe" scripts\origin_smoke_test.py`
- Test: `python -m unittest discover -s tests`
- Evaluate intake: `python scripts\evaluate_intake_cases.py --planner rule`
- Qwen smoke test: `python scripts\qwen_smoke_test.py --model qwen3.7-max`
- Guardrails: `python scripts\check_guardrails.py --policy .codex\harness-policy.json`
- Lint/typecheck: not configured yet.

## Architecture

- Main entry points: `src/origin_ai_lab/cli.py`, `scripts/origin_smoke_test.py`.
- Web UI entry point: `src/origin_ai_lab/web_server.py`, serving static files from `web/`.
- Important modules:
  - `models.py`: typed task, profile, and result contracts.
  - `agents/requirement_intake.py`: natural-language request intake and slot extraction.
  - `agents/qwen_planner.py`: Alibaba Cloud Model Studio / Qwen OpenAI-compatible planner.
  - `agents/planner_adapter.py`: planner selection and rule fallback.
  - `connectors/csv_table.py`: file ingest and lightweight profiling.
  - `connectors/origin_client.py`: optional Origin/OriginPro automation boundary.
  - `connectors/python_analysis.py`: deterministic analysis routines.
  - `agents/planner.py`: rule-based placeholder for the future LLM planner.
  - `evaluation/checks.py`: reproducibility and sanity checks.
  - `workflows/analyze_and_plot.py`: first end-to-end workflow.
  - `web_server.py`: local stdlib HTTP API and static frontend server.
- Data flow: user intent and dataset -> profile -> plan -> deterministic analysis -> validation -> plot spec/Origin project/artifacts.
- External services: none required for the current scaffold. Optional Qwen planner reads `DASHSCOPE_API_KEY` from environment only.
- Persistence: local run folders under `runs/`, with JSON reports and plot specs; Origin outputs are generated only when Origin is available.

## Coding Conventions

- Language/runtime: Python 3.10+; keep core modules usable without Origin installed.
- Formatting: small, explicit modules; avoid large framework commitments before the MVP stabilizes.
- Error handling: distinguish user data errors, validation failures, and unavailable external software.
- Testing: unit-test deterministic logic without Origin; smoke-test Origin separately on Windows machines with a license.
- Logging: prefer structured artifact files for reproducibility; add runtime logging once a service layer exists.

## Hard Project Rules

- Do not store API keys, license files, raw confidential research data, or instrument exports in the repo.
- Do not let the AI directly mutate Origin projects without a validated plan and an artifact log.
- Do not treat a generated plot as accepted until numeric checks and user-facing assumptions are recorded.
- Do not make cloud AI the only path; private labs need a local/offline or bring-your-own-model option.
- Do not change public task/result schemas without updating docs and tests.

## Known Pitfalls

- `originpro` launches a local Origin instance and is Windows-only for external Python automation.
- COM/Origin failures can leave an Origin process open; keep Origin visible during development.
- Scientific plots can look plausible while the analysis method is wrong. Tests need golden datasets and method-specific invariants.
- Repeated GUI automation is brittle; prefer `originpro`, Analysis Templates, LabTalk, and Origin project templates before screen control.
- Python 3.14 may be ahead of some scientific packages; prefer the dedicated Origin environment for Origin smoke tests.

## Review Gates

- Direction: use `$hermes-debate-jury` for ambiguous architecture, product scope, or scientific-validation strategy.
- Security/privacy: review auth, secrets, dataset handling, trace retention, and cloud-provider choices.
- Reliability: review retries, process cleanup, Origin availability, queue behavior, and reproducibility.
- Scientific validity: every new analysis workflow needs a known dataset, expected numerical checks, and failure cases.
- Release: verify tests/build and document any unverified risk.

## Definition Of Done

- Implementation matches the stated acceptance criteria.
- Relevant tests/checks have been run or the reason they could not run is documented.
- Generated artifacts are reproducible from committed code and sample inputs.
- Risky assumptions are called out.
- Durable lessons are proposed for `AGENTS.md`, `SOUL.md`, skills, scripts, or docs only after review.
