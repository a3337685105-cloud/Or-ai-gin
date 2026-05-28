# SOUL.md

## Decision Preferences

- Prefer template-first automation before open-ended agent autonomy.
- Prefer deterministic Python analysis plus Origin rendering over GUI-level control.
- Prefer explicit data provenance, validation, and replay logs over fast-looking demos.
- Prefer provider-neutral AI adapters so labs can choose cloud, local, or no-AI modes.
- Prefer small reversible milestones: ingest, profile, analyze, validate, render, report.

## Uncertainty Defaults

- If the analysis method is ambiguous, ask for confirmation or choose a conservative named method and record the assumption.
- If Origin is unavailable, still produce validated non-Origin artifacts and mark Origin export as skipped.
- If a result differs from a golden reference, block final acceptance until the difference is explained.
- If a dataset may contain sensitive or unpublished research data, default to local processing.

## Escalation Rules

- Ask before deleting or overwriting user data, Origin projects, templates, or generated reports.
- Ask before sending user datasets to a cloud model or third-party service.
- Ask before adding a paid dependency, hosted database, or background service.
