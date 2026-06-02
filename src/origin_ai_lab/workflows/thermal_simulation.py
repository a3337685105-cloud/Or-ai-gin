from __future__ import annotations

import csv
import json
from pathlib import Path

from origin_ai_lab.connectors.comsol_client import ComsolThermalClient, ComsolUnavailable
from origin_ai_lab.models import (
    CheckResult,
    SimulationBackend,
    ThermalSimulationResult,
    ThermalSimulationTask,
)
from origin_ai_lab.simulations.thermal import (
    build_thermal_execution_plan,
    build_thermal_spec,
    evaluate_thermal_metrics,
    run_mock_thermal_solver,
    validate_thermal_spec,
)
from origin_ai_lab.visualization.thermal import (
    build_default_thermal_visualization_spec,
    build_thermal_visualization_manifest,
    evaluate_visualization_manifest_quality,
    evaluate_visualization_spec,
)


def run_thermal_simulation(task: ThermalSimulationTask, output_dir: Path) -> ThermalSimulationResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    spec = build_thermal_spec(task)
    checks = validate_thermal_spec(spec)
    artifacts: dict[str, str] = {}
    metrics: dict[str, object] = {}
    status = "planned"

    spec_path = output_dir / "thermal_simulation_spec.json"
    spec_path.write_text(json.dumps(spec.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts["thermal_simulation_spec"] = str(spec_path)

    plan = build_thermal_execution_plan(spec)
    plan_path = output_dir / "thermal_execution_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts["thermal_execution_plan"] = str(plan_path)

    error_checks_passed = all(check.passed for check in checks if check.severity == "error")
    if error_checks_passed and spec.backend == SimulationBackend.MOCK:
        metrics = run_mock_thermal_solver(spec)
        checks.extend(evaluate_thermal_metrics(metrics))
        summary_path = output_dir / "thermal_summary.csv"
        _write_metrics_csv(summary_path, metrics)
        artifacts["thermal_summary_csv"] = str(summary_path)
        status = "mock-complete"
    elif error_checks_passed and spec.backend == SimulationBackend.DRY_RUN:
        checks.append(
            CheckResult(
                name="thermal_solver_not_run",
                passed=True,
                message="Dry-run backend recorded the plan without solving.",
                severity="warning",
            )
        )
        status = "dry-run"
    elif error_checks_passed and spec.backend == SimulationBackend.COMSOL:
        try:
            metrics = ComsolThermalClient().run_thermal_study(spec, output_dir)
            checks.extend(evaluate_thermal_metrics(metrics))
            for key in ("output_mph", "batch_log", "status_file"):
                value = metrics.get(key)
                if isinstance(value, str) and value:
                    artifacts[f"comsol_{key}"] = value
            status = "comsol-complete"
        except ComsolUnavailable as exc:
            checks.append(
                CheckResult(
                    name="comsol_execution_available",
                    passed=False,
                    message=str(exc),
                )
            )
            status = "blocked"
    else:
        status = "invalid"

    visualization_spec = build_default_thermal_visualization_spec(spec, dict(metrics))
    visualization_spec_path = output_dir / "thermal_visualization_spec.json"
    visualization_spec_path.write_text(
        json.dumps(visualization_spec.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    artifacts["thermal_visualization_spec"] = str(visualization_spec_path)

    visualization_manifest = build_thermal_visualization_manifest(visualization_spec, output_dir)
    visualization_manifest_path = output_dir / "thermal_visualization_manifest.json"
    visualization_manifest_path.write_text(
        json.dumps(visualization_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    artifacts["thermal_visualization_manifest"] = str(visualization_manifest_path)

    visualization_checks = evaluate_visualization_spec(visualization_spec)
    visualization_checks.extend(evaluate_visualization_manifest_quality(visualization_manifest))
    checks.extend(visualization_checks)
    visualization_quality_report = {
        "schema_version": "thermal-visualization-quality/v1",
        "manifest_path": str(visualization_manifest_path),
        "checks": [check.to_dict() for check in visualization_checks],
        "passed": all(check.passed for check in visualization_checks if check.severity == "error"),
    }
    visualization_quality_path = output_dir / "thermal_visualization_quality.json"
    visualization_quality_path.write_text(
        json.dumps(visualization_quality_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    artifacts["thermal_visualization_quality"] = str(visualization_quality_path)

    result = ThermalSimulationResult(
        spec=spec,
        checks=checks,
        metrics=dict(metrics),
        artifacts=artifacts,
        status=status,
    )
    result_path = output_dir / "thermal_result.json"
    artifacts["thermal_result"] = str(result_path)
    result_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def _write_metrics_csv(path: Path, metrics: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["metric", "value"])
        for key, value in metrics.items():
            writer.writerow([key, value])
