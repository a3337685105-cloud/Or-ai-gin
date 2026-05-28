# Origin Assistant Execution Plan

## Product Boundary

This project is an AI operating layer for Origin/OriginPro. It should help users
apply Origin well, not replace domain-specialized packages such as JADE,
HighScore, instrument-control software, or database-backed phase-identification
systems.

## Operating Principle

AI may interpret, propose, and summarize. Deterministic code must validate,
execute, and record every Origin-facing action.

The product should feel like an extra skilled hand:

- The user speaks in natural language.
- The system converts the request into editable slots and a validated plan.
- Origin performs the final project/graph/export work.
- Every run produces artifacts, checks, and a revision trail.

## Workstream Order

### P0. Origin Execution Completeness

Goal: make common `PlotSpec` fields actually affect Origin output.

Deliverables:

- Apply series color, marker, marker size, and line width.
- Apply fit-line color and line width.
- Apply x/y axis limits.
- Export requested PNG/SVG/PDF formats and always keep an OPJU project.
- Record Origin render metadata for checks and UI display.

Acceptance:

- A spec/edit request such as "red line, x 0-10, export svg" creates matching
  Origin artifacts.
- Existing no-Origin tests still pass.
- At least one real Origin smoke run verifies exported files and metadata.

### P1. Editable Requirement Card

Goal: let users correct AI understanding before running Origin.

Deliverables:

- Frontend slots for plot type, x/y/group, fit enabled, titles, output formats.
- Backend accepts explicit slot overrides from the UI.
- Clarifying questions remain focused on blocking ambiguity only.

Acceptance:

- User can run without rephrasing the whole prompt after changing a slot.
- The final `PlotSpec` records both AI assumptions and user overrides.

### P2. Origin-Native Template Pack

Goal: cover tasks that researchers commonly complete in Origin.

Initial templates:

- XY scatter/line with optional linear fit.
- Multi-curve and stacked spectra.
- Error-bar plot.
- Peak-marked spectrum.
- CV curve plot and peak summary.
- Nyquist plot.
- TGA/DSC curve.
- Stress-strain curve.

Non-goals:

- XRD PDF database search/match.
- Rietveld refinement.
- Spectral library identification.
- EIS equivalent-circuit fitting unless explicitly backed by an Origin workflow
  or external connector later.

### P3. Instrument Export Robustness

Goal: make real lab exports easy to import into Origin workflows.

Deliverables:

- More CSV/TXT dialect fixtures.
- Excel multi-sheet support.
- Unit-row and metadata-row detection.
- Multi-segment scan detection with a clarification or split plan.

Acceptance:

- Parser produces a normalized CSV/worksheet plan without mutating raw data.
- Ambiguous multi-table files ask the user which segment to use.

### P4. Origin Analysis Tool Adapters

Goal: expose Origin's own analysis power through validated wrappers.

Initial adapters:

- Curve fitting.
- Peak Analyzer style baseline/peak output.
- Batch processing via templates.
- Selected Origin Apps only when they are local and automatable.

Acceptance:

- Each adapter has a schema, golden dataset, expected numeric checks, and Origin
  artifact verification.

### P5. Accuracy And Feedback Loop

Goal: convert failed or corrected outputs into eval cases.

Deliverables:

- Export-format checks.
- OCR/object checks for axis labels and legend text.
- User feedback capture: original request, AI plan, result, correction.
- Evaluation scripts for multi-turn edit workflows.

Acceptance:

- A failed user correction can be replayed as an automated eval.

## Automation Cadence

For each workstream:

1. Implement the smallest useful vertical slice.
2. Add deterministic tests or eval cases.
3. Run no-Origin tests.
4. Run one Origin smoke test when the change touches Origin.
5. Record known gaps in this document or a focused design note.

Ask the user only for product-direction changes, access to non-local data, or
decisions that cannot be inferred from the Origin-only boundary.

## Implementation Status 2026-05-28

Completed vertical slices:

- P0: common `PlotSpec` fields now affect Origin output for color/style,
  fit-line rendering, axis limits, requested image formats, OPJU output, and
  Origin render metadata.
- P1: the web UI exposes editable slots for plot type, x/y/group columns,
  titles, fit toggle, and output formats; `/api/analyze` accepts validated
  overrides from those slots.
- P2: task-to-Origin template selection now records an `origin_template.json`
  artifact and keeps material workflows such as XRD/Raman/TGA/DSC inside
  Origin plotting scope instead of drifting into database-backed analysis.
- P3: the table loader handles metadata rows, unit rows, tab/comma text files,
  and first-sheet XLSX exports, then writes a normalized CSV for Origin.
- P4: workflow runs now record `origin_analysis_adapters.json`; current
  adapters cover Origin graph export, linear-fit overlay, and spectrum peak
  marker handoff.
- P5: workflow checks cover export formats, axis-title intent, fit/peak
  expectations, visual nonblank/content checks, and user correction capture via
  `/api/feedback`.
- Style defaults: `origin-ai-clean-v1` adds professional axis-title inference,
  cleaner single-series legend policy, stronger line/marker defaults, larger
  export width, and material-spectrum peak marker styling.

Verified:

- `python -m unittest discover -s tests`
- `python scripts\evaluate_route_cases.py --planner rule`
- `python scripts\evaluate_intake_cases.py --planner rule`
- `python scripts\evaluate_modify_cases.py --planner rule`
- `python scripts\qwen_smoke_test.py --model qwen3.7-max`
- `python scripts\check_guardrails.py --policy .codex\harness-policy.json`
- Real Origin smoke: `runs\origin_smoke`
- Real Origin XRD template smoke: `runs\origin_xrd_template_smoke`

MVP gates:

- Multi-turn plot modification and deterministic visual quality checks are now
  explicit MVP acceptance gates in `docs/mvp_acceptance.md`.

Remaining adapter depth:

- Native Origin Peak Analyzer baseline reports, batch Analysis Template
  execution, and automatable Origin Apps still need dedicated wrappers, golden
  datasets, and numeric invariants before they should be exposed as production
  operations.
