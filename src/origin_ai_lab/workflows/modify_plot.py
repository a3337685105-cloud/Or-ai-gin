from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from origin_ai_lab.agents.qwen_edit_planner import infer_edit_plan_auto
from origin_ai_lab.connectors.csv_table import numeric_pairs, profile_csv
from origin_ai_lab.models import AnalysisTask, PlotEditPlan, PlotSpec, TaskType
from origin_ai_lab.plotting.spec_editor import apply_edit_plan, validate_plot_spec
from origin_ai_lab.workflows.analyze_and_plot import run_analysis


def create_initial_plot_revision(task: AnalysisTask, runs_root: Path, run_id: str | None = None) -> dict[str, Any]:
    active_run_id = run_id or _new_run_id()
    run_dir = runs_root / active_run_id
    revision = 0
    output_dir = _revision_dir(run_dir, revision)
    result = run_analysis(task, output_dir)
    if result.plot_spec is None:
        raise RuntimeError("Initial workflow did not produce a plot spec.")
    manifest = {
        "run_id": active_run_id,
        "dataset_path": str(task.dataset_path),
        "initial_request": task.goal,
        "latest_revision": revision,
        "revisions": [
            _revision_record(active_run_id, revision, task.goal, output_dir, result.artifacts),
        ],
    }
    _write_manifest(run_dir, manifest)
    return {
        "run_id": active_run_id,
        "revision": revision,
        "manifest": manifest,
        "plot_spec": result.plot_spec,
        "result": result,
        "points": points_for_spec(result.plot_spec),
    }


def modify_plot_revision(
    run_id: str,
    request: str,
    runs_root: Path,
    revision: int | None = None,
    use_origin: bool = False,
) -> dict[str, Any]:
    run_dir = _safe_run_dir(runs_root, run_id)
    manifest = _read_manifest(run_dir)
    base_revision = int(manifest["latest_revision"] if revision is None else revision)
    base_spec = _read_plot_spec(_revision_dir(run_dir, base_revision) / "plot_spec.json")
    profile = profile_csv(base_spec.dataset_path)
    edit_plan = infer_edit_plan_auto(request, base_spec, profile)
    if not edit_plan.ready_to_execute:
        return {
            "run_id": run_id,
            "base_revision": base_revision,
            "revision": base_revision,
            "edit_plan": edit_plan,
            "plot_spec": base_spec,
            "result": None,
            "points": points_for_spec(base_spec),
            "manifest": manifest,
            "artifacts": {},
        }
    new_spec = apply_edit_plan(base_spec, edit_plan, profile)
    validate_plot_spec(new_spec, profile)
    new_revision = int(manifest["latest_revision"]) + 1
    output_dir = _revision_dir(run_dir, new_revision)
    task = AnalysisTask(
        dataset_path=new_spec.dataset_path,
        goal=request,
        task_type=TaskType.PLOT_XY,
        x_column=new_spec.x_column,
        y_column=new_spec.y_column,
        group_column=new_spec.group_column,
        plot_kind=new_spec.plot_kind,
        style=new_spec.style,
        output_formats=new_spec.output_formats,
        fit_enabled=new_spec.fit_enabled,
        use_origin=use_origin,
    )
    result = run_analysis(task, output_dir, plot_spec=new_spec)
    edit_plan_path = output_dir / "edit_plan.json"
    edit_plan_path.write_text(json.dumps(edit_plan.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    result.artifacts["edit_plan"] = str(edit_plan_path)
    result_path = output_dir / "result.json"
    result_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["latest_revision"] = new_revision
    manifest.setdefault("revisions", []).append(
        _revision_record(run_id, new_revision, request, output_dir, result.artifacts, base_revision)
    )
    _write_manifest(run_dir, manifest)
    return {
        "run_id": run_id,
        "base_revision": base_revision,
        "revision": new_revision,
        "edit_plan": edit_plan,
        "plot_spec": new_spec,
        "result": result,
        "points": points_for_spec(new_spec),
        "manifest": manifest,
        "artifacts": result.artifacts,
    }


def load_plot_revision(run_id: str, revision: int, runs_root: Path) -> dict[str, Any]:
    run_dir = _safe_run_dir(runs_root, run_id)
    manifest = _read_manifest(run_dir)
    output_dir = _revision_dir(run_dir, revision)
    spec = _read_plot_spec(output_dir / "plot_spec.json")
    result_path = output_dir / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
    artifacts = result.get("artifacts", {}) if isinstance(result, dict) else {}
    return {
        "run_id": run_id,
        "revision": revision,
        "manifest": manifest,
        "plot_spec": spec,
        "result": result,
        "points": points_for_spec(spec),
        "artifacts": artifacts,
    }


def points_for_spec(spec: PlotSpec, limit: int = 200) -> list[tuple[float, float]]:
    if not spec.x_column or not spec.y_column:
        return []
    try:
        return numeric_pairs(spec.dataset_path, spec.x_column, spec.y_column)[:limit]
    except Exception:
        return []


def _new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")


def _revision_dir(run_dir: Path, revision: int) -> Path:
    return run_dir / "revisions" / f"{revision:04d}"


def _revision_record(
    run_id: str,
    revision: int,
    request: str,
    output_dir: Path,
    artifacts: dict[str, str],
    base_revision: int | None = None,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "revision": revision,
        "base_revision": base_revision,
        "request": request,
        "output_dir": str(output_dir),
        "artifacts": artifacts,
    }


def _manifest_path(run_dir: Path) -> Path:
    return run_dir / "run_manifest.json"


def _read_manifest(run_dir: Path) -> dict[str, Any]:
    path = _manifest_path(run_dir)
    if not path.exists():
        raise FileNotFoundError(f"Run manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    _manifest_path(run_dir).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_plot_spec(path: Path) -> PlotSpec:
    if not path.exists():
        raise FileNotFoundError(f"Plot spec not found: {path}")
    return PlotSpec.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _safe_run_dir(runs_root: Path, run_id: str) -> Path:
    if not run_id or any(char in run_id for char in "\\/.:"):
        raise ValueError("Invalid run_id.")
    run_dir = (runs_root / run_id).resolve()
    run_dir.relative_to(runs_root.resolve())
    return run_dir
