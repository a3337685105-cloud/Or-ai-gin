# Parallel Work Package

This package is meant to let multiple Codex conversations work in parallel without losing the
single-product direction.

The product direction is:

```text
one user-facing research assistant
-> thick intake
-> thin work order
-> simulation/analysis execution
-> visualization/report/evidence package
```

Do not create separate product entrances for COMSOL, Origin, reporting, animation, or V&V.
Those are internal capabilities behind the same assistant workflow.

## Recommended Branches

| Branch | Purpose |
| --- | --- |
| `codex/research-assistant-core` | Stabilize current foundation and docs before parallel feature work. |
| `codex/unified-research-intake` | Build the thick-to-thin intake and single work-order contract. |
| `codex/comsol-result-export` | Export usable COMSOL results, not just solved `.mph` files. |
| `codex/thermal-visual-package` | Produce thermal figures, animations, and visualization manifests. |
| `codex/simulation-report-builder` | Build evidence-based Markdown/HTML simulation reports. |
| `codex/thermal-vv-harness` | Add validation, golden cases, log parsing, and credibility checks. |
| `codex/research-assistant-workbench` | Make the frontend a single-entry research assistant workbench. |

## Important Base-Branch Rule

Before creating parallel branches, create a clean base commit or base branch that includes the
current shared foundation. If you create worktrees from `HEAD` while the main workspace has
uncommitted changes, those changes will not appear in the worktrees.

Good workflow:

```powershell
git status
git checkout -b codex/research-assistant-core
git add README.md docs src tests scripts
git commit -m "Build research assistant simulation foundation"
```

Then create worktrees or new Codex conversations from that branch.

If you do not want to commit yet, do not use worktrees for feature work from the current dirty
workspace. Ask one Codex conversation to first make the baseline branch/commit.

## Worktree Or Normal Branch?

Use normal branches when:

- you are working in one conversation at a time;
- you do not need multiple local folders open simultaneously.

Use `git worktree` when:

- you want several Codex conversations working in parallel;
- each conversation needs its own clean folder;
- you want to run tests in each branch without switching the main workspace.

Worktree mental model:

```text
one git repository
many checked-out folders
each folder can be on a different branch
```

Example:

```powershell
git worktree add ..\origin-ai-worktrees\intake codex/unified-research-intake
git worktree add ..\origin-ai-worktrees\comsol-export codex/comsol-result-export
```

Or use:

```powershell
.\scripts\create_research_assistant_worktrees.ps1 -BaseRef codex/research-assistant-core
```

## Merge Order

Recommended order:

1. `codex/research-assistant-core`
2. `codex/unified-research-intake`
3. `codex/comsol-result-export`
4. `codex/thermal-vv-harness`
5. `codex/thermal-visual-package`
6. `codex/simulation-report-builder`
7. `codex/research-assistant-workbench`

This order keeps contracts stable before UI/reporting depends on them.

## Shared Contracts

All branches should converge on these internal artifacts:

- `ResearchWorkOrder`
- `SimulationSpec`
- `VisualizationSpec`
- `ReportManifest`
- `EvidenceTrace`

If a branch needs a new contract, it should document the change and include tests.

