# Origin AI Lab

Origin AI Lab is the current working name for a single-entry scientific research
assistant. The product should not expose separate COMSOL, Origin, reporting,
animation, or V&V modes to users. The user starts with one front door:

```text
research goal + optional files + desired output
```

Internally, the assistant preserves thick user context, compresses it into a
thin `ResearchWorkOrder`, routes to simulation or analysis tools, then returns
figures, animations, reports, and validation evidence as one reproducible
result package.

The implementation stays conservative: AI proposes and explains; deterministic
tools ingest data, run analysis/simulation, validate outputs, and write
artifact logs. Origin and COMSOL are Windows-local worker capabilities behind
guarded connectors, so the core test suite still runs without licensed desktop
software.

## Current Status

- Single assistant direction: `docs/research_assistant_product_design.md`
- Architecture route: `docs/architecture.md`
- Design principles: `docs/design_principles.md`
- Feasibility report: `docs/feasibility_report.md`
- Roadmap: `docs/roadmap.md`
- MVP acceptance gates: `docs/mvp_acceptance.md`
- Research intake case findings: `docs/research_intake_case_study_findings.md`
- Requirement intake design: `docs/requirement_intake_design.md`
- AI integration note: `docs/ai_integration.md`
- Plot modification design: `docs/plot_modification_design.md`
- Plot accuracy QA: `docs/plot_accuracy_design.md`
- Visual quality QA: `docs/visual_quality_design.md`
- Thermal simulation scaffold: `docs/thermal_simulation_design.md`
- Thermal report/evidence design: `docs/thermal_report_capability_design.md`
- Evaluation report: `docs/evaluation_report.md`
- Parallel work package: `docs/parallel_work/README.md`
- Branch task cards: `docs/parallel_work/BRANCH_TASKS.md`
- Ready-to-copy branch prompts: `docs/parallel_work/PROMPTS.md`
- Workflow templates: `docs/workflow/WORK_ORDER.template.md`, `docs/workflow/WORKFLOW_AUDIT.template.md`

## Current Foundation

| Capability | Main code | Test coverage |
| --- | --- | --- |
| Thick-to-thin research intake | `src/origin_ai_lab/agents/research_intake_harness.py` | `tests/test_workflow.py` |
| CSV/profile/plot workflow | `src/origin_ai_lab/workflows/analyze_and_plot.py` | `tests/test_workflow.py` |
| Plot revisions | `src/origin_ai_lab/workflows/modify_plot.py` | `tests/test_workflow.py` |
| Origin boundary | `src/origin_ai_lab/connectors/origin_client.py` | Unit tests avoid requiring Origin |
| COMSOL discovery and batch boundary | `src/origin_ai_lab/connectors/software_discovery.py`, `src/origin_ai_lab/connectors/comsol_client.py` | Mock/dry-run/unit coverage |
| Thermal simulation scaffold | `src/origin_ai_lab/workflows/thermal_simulation.py` | `tests/test_workflow.py` |
| Thermal validation harness | `src/origin_ai_lab/simulations/thermal_harness.py` | `tests/test_workflow.py` |
| Local web server | `src/origin_ai_lab/web_server.py`, `web/` | API helper tests |

## Easiest Start

For Windows local use:

```powershell
.\scripts\setup_windows.ps1
.\scripts\start_web.ps1
```

For the quickest daily launch, double-click `start_origin_ai_lab.bat` or run:

```powershell
.\start_origin_ai_lab.bat
```

If PowerShell blocks local scripts, run the same setup with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\start_web.ps1
```

The web UI opens at:

```text
http://127.0.0.1:8765
```

No cloud key is required for the rule-based planner. In the web UI, use the "模型与密钥" panel only when you want Qwen planning.

## Developer Commands

These commands are for developers to verify internal capabilities. They are not
intended to become separate user-facing product modes.

```powershell
python -m pip install -e .
```

Single-entry research intake:

```powershell
python -m origin_ai_lab.cli research-intake "我想判断5W芯片贴在铝板上会不会超过80度，先给我自己判断方向用"
python -m origin_ai_lab.cli research-intake --question-bank
```

Plotting/analysis baseline:

```powershell
python -m origin_ai_lab.cli intake "帮我画散点图，加线性拟合，导出 png" --dataset examples\sample_xy.csv
origin-ai analyze examples/sample_xy.csv --out runs/demo --no-origin
```

Thermal/COMSOL internal capability checks:

```powershell
origin-ai doctor
origin-ai thermal --backend mock --out runs/thermal_demo --param chip_power_W=5 --param ambient_temp_C=25 --param h_conv_W_m2K=10
origin-ai thermal-harness --backend dry-run --case busbar_smoke --case chip_cooling_reference
```

Evaluation and tests:

```powershell
python scripts\evaluate_intake_cases.py --planner rule
python scripts\evaluate_route_cases.py --planner rule
python scripts\evaluate_modify_cases.py --planner rule
python scripts\qwen_smoke_test.py --model qwen3.7-max
python -m unittest discover -s tests
python scripts\check_guardrails.py --policy .codex\harness-policy.json
```

If `origin-ai` is not on `PATH` after editable install, use the module entry point:

```powershell
python -m origin_ai_lab.cli analyze examples\sample_xy.csv --out runs/demo --no-origin
```

Run the local web UI:

```powershell
$env:PYTHONPATH='src'; python -m origin_ai_lab.web_server
```

Then open:

```text
http://127.0.0.1:8765
```

In the web UI, use the "模型与密钥" panel to save a DashScope key locally. The key is encrypted with Windows DPAPI and is not stored in the repository.

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
