from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from origin_ai_lab.models import CheckResult, ThermalSimulationResult


GENERATED_REPORT_ARTIFACT_KEYS = {
    "thermal_report_manifest",
    "thermal_report_markdown",
    "thermal_report_html",
    "thermal_artifact_index",
    "thermal_evidence_gaps",
}

REPORT_SECTIONS = (
    ("summary_conclusion_boundary", "Summary and conclusion boundary"),
    ("user_goal_criteria", "User goal and criteria"),
    ("inputs_assumptions_physics", "Inputs, assumptions, materials, heat sources, and boundaries"),
    ("model_solver_software", "Model, solver, and software versions"),
    ("results_figures_tables", "Result figures and numeric tables"),
    ("validation_risks", "Validation status and risks"),
    ("reproducibility_index", "File, log, and reproducibility index"),
)


@dataclass(frozen=True)
class ThermalReportPackage:
    manifest_path: Path
    report_path: Path
    artifact_index_path: Path
    evidence_gaps_path: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "thermal_report_manifest": str(self.manifest_path),
            "thermal_report_markdown" if self.report_path.suffix.lower() == ".md" else "thermal_report_html": str(
                self.report_path
            ),
            "thermal_artifact_index": str(self.artifact_index_path),
            "thermal_evidence_gaps": str(self.evidence_gaps_path),
        }


def build_thermal_report_package(
    *,
    output_dir: Path,
    work_order: Any | None,
    thermal_result: ThermalSimulationResult | dict[str, Any],
    visualization_manifest: dict[str, Any] | None = None,
    external_artifacts: dict[str, str] | None = None,
    validation_checks: Sequence[CheckResult | dict[str, Any]] = (),
    report_format: str = "markdown",
) -> ThermalReportPackage:
    """Write a scientist-facing thermal report package.

    The builder treats missing evidence as reportable data. It can operate with
    only the mock thermal result, but the generated manifest will mark the
    sections that are incomplete for presentation or external claims.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = _utc_now()
    result_data = _to_mapping(thermal_result)
    work_order_data = _to_mapping(work_order) if work_order is not None else {}
    checks = _deduplicate_checks(
        [*_checks_from_result(result_data), *[_check_to_dict(check) for check in validation_checks]]
    )
    spec = result_data.get("spec") if isinstance(result_data.get("spec"), dict) else {}
    metrics = result_data.get("metrics") if isinstance(result_data.get("metrics"), dict) else {}
    visualization = visualization_manifest if isinstance(visualization_manifest, dict) else {}

    artifact_index_path = output_dir / "artifact_index.json"
    evidence_gaps_path = output_dir / "evidence_gaps.json"
    manifest_path = output_dir / "thermal_report_manifest.json"
    report_path = output_dir / ("thermal_report.html" if report_format == "html" else "thermal_report.md")

    source_artifacts = _collect_source_artifacts(
        output_dir=output_dir,
        result_data=result_data,
        visualization_manifest=visualization,
        external_artifacts=external_artifacts or {},
    )
    sections, gaps = _build_sections_and_gaps(
        work_order=work_order_data,
        result=result_data,
        spec=spec,
        metrics=metrics,
        checks=checks,
        visualization_manifest=visualization,
        artifact_items=source_artifacts,
    )
    report_modes = _report_modes(result_data, checks, gaps, visualization)
    summary = _summary_data(work_order_data, result_data, spec, metrics)

    report_text = _render_markdown_report(
        generated_at=generated_at,
        work_order=work_order_data,
        result=result_data,
        spec=spec,
        metrics=metrics,
        checks=checks,
        visualization_manifest=visualization,
        artifact_items=source_artifacts,
        sections=sections,
        gaps=gaps,
        report_modes=report_modes,
        summary=summary,
    )
    if report_format == "html":
        report_path.write_text(_markdown_to_simple_html(report_text), encoding="utf-8")
    else:
        report_path.write_text(report_text, encoding="utf-8")

    evidence_gap_list = {
        "schema_version": "thermal-evidence-gap-list/v1",
        "generated_at_utc": generated_at,
        "gap_count": len(gaps),
        "gaps": gaps,
    }
    evidence_gaps_path.write_text(json.dumps(evidence_gap_list, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "schema_version": "thermal-report-manifest/v1",
        "generated_at_utc": generated_at,
        "report": {
            "format": "html" if report_format == "html" else "markdown",
            "path": str(report_path),
            "title": "Thermal Simulation Report",
        },
        "source_inputs": {
            "research_work_order": _input_status(bool(work_order_data), "ResearchWorkOrder"),
            "thermal_simulation_result": _input_status(bool(result_data), "thermal_simulation_result"),
            "visualization_manifest": _input_status(bool(visualization), "visualization manifest"),
            "comsol_origin_artifacts": _input_status(_has_comsol_or_origin_artifacts(source_artifacts), "COMSOL/Origin artifacts"),
            "validation_checks": {
                "status": "complete" if checks else "missing",
                "count": len(checks),
                "passed": _checks_passed(checks),
            },
        },
        "summary": summary,
        "report_modes": report_modes,
        "sections": sections,
        "artifact_index_path": str(artifact_index_path),
        "evidence_gaps_path": str(evidence_gaps_path),
        "gap_count": len(gaps),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    generated_artifacts = [
        _artifact_item("thermal_report_manifest", "generated_report_manifest", manifest_path, output_dir),
        _artifact_item("thermal_report", "generated_report", report_path, output_dir),
        _artifact_item("evidence_gaps", "generated_evidence_gap_list", evidence_gaps_path, output_dir),
        _artifact_item("artifact_index", "generated_artifact_index", artifact_index_path, output_dir, self_reference=True),
    ]
    artifact_index = {
        "schema_version": "thermal-artifact-index/v1",
        "generated_at_utc": generated_at,
        "artifact_count": len(source_artifacts) + len(generated_artifacts),
        "artifacts": source_artifacts + generated_artifacts,
        "missing_artifacts": [
            item for item in source_artifacts + generated_artifacts if not item.get("exists")
        ],
    }
    artifact_index_path.write_text(json.dumps(artifact_index, ensure_ascii=False, indent=2), encoding="utf-8")

    return ThermalReportPackage(
        manifest_path=manifest_path,
        report_path=report_path,
        artifact_index_path=artifact_index_path,
        evidence_gaps_path=evidence_gaps_path,
    )


def _build_sections_and_gaps(
    *,
    work_order: dict[str, Any],
    result: dict[str, Any],
    spec: dict[str, Any],
    metrics: dict[str, Any],
    checks: list[dict[str, Any]],
    visualization_manifest: dict[str, Any],
    artifact_items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    gaps: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []

    def add_gap(
        section_id: str,
        gap_id: str,
        message: str,
        severity: str,
        needed_for: Iterable[str],
    ) -> None:
        gaps.append(
            {
                "id": gap_id,
                "section": section_id,
                "severity": severity,
                "message": message,
                "needed_for": list(needed_for),
            }
        )

    if not work_order:
        add_gap(
            "user_goal_criteria",
            "research_work_order_missing",
            "No ResearchWorkOrder was supplied, so user intent and acceptance criteria are incomplete.",
            "warning",
            ("internal_judgment", "presentation", "paper_external_claim"),
        )
    criterion = _decision_criterion(work_order)
    if criterion in ("", "not_declared", "mentioned_in_goal_text"):
        add_gap(
            "user_goal_criteria",
            "acceptance_criteria_not_explicit",
            "No explicit numeric or textual acceptance criterion was recorded.",
            "warning",
            ("internal_judgment", "presentation", "paper_external_claim"),
        )

    context = work_order.get("thick_context") if isinstance(work_order.get("thick_context"), dict) else {}
    if not (context.get("geometry") or spec.get("template_path")):
        add_gap(
            "inputs_assumptions_physics",
            "geometry_evidence_missing",
            "Geometry evidence is not linked to a CAD, COMSOL template, or user-confirmed simplified model.",
            "warning",
            ("presentation", "paper_external_claim"),
        )
    if not context.get("materials"):
        add_gap(
            "inputs_assumptions_physics",
            "material_table_missing",
            "Material identities and thermal property sources are not recorded.",
            "blocking",
            ("presentation", "paper_external_claim"),
        )
    if not _parameter_named(spec, "chip_power_W") and not context.get("heat_sources"):
        add_gap(
            "inputs_assumptions_physics",
            "heat_source_missing",
            "No heat-source magnitude or location evidence was found.",
            "blocking",
            ("internal_judgment", "presentation", "paper_external_claim"),
        )
    if not (_parameter_named(spec, "h_conv_W_m2K") or context.get("cooling_boundaries")):
        add_gap(
            "inputs_assumptions_physics",
            "boundary_condition_missing",
            "No thermal sink or boundary-condition evidence was found.",
            "blocking",
            ("internal_judgment", "presentation", "paper_external_claim"),
        )

    if not result:
        add_gap(
            "summary_conclusion_boundary",
            "thermal_result_missing",
            "No thermal simulation result was supplied.",
            "blocking",
            ("internal_judgment", "presentation", "paper_external_claim"),
        )
    if not metrics:
        add_gap(
            "results_figures_tables",
            "numeric_metrics_missing",
            "No numeric thermal metrics were supplied.",
            "blocking",
            ("internal_judgment", "presentation", "paper_external_claim"),
        )
    if not _has_summary_table(artifact_items):
        add_gap(
            "results_figures_tables",
            "numeric_table_artifact_missing",
            "No result table artifact such as thermal_summary.csv is indexed.",
            "warning",
            ("presentation", "paper_external_claim"),
        )
    if not visualization_manifest:
        add_gap(
            "results_figures_tables",
            "visualization_manifest_missing",
            "No visualization manifest was supplied; field/slice/flux figures cannot be audited.",
            "warning",
            ("presentation", "paper_external_claim"),
        )
    elif not _visualization_items(visualization_manifest):
        add_gap(
            "results_figures_tables",
            "visualization_items_missing",
            "The visualization manifest has no figures, tables, animations, or image artifacts.",
            "warning",
            ("presentation", "paper_external_claim"),
        )

    if not checks:
        add_gap(
            "validation_risks",
            "validation_checks_missing",
            "No validation checks were supplied.",
            "blocking",
            ("internal_judgment", "presentation", "paper_external_claim"),
        )
    for check in checks:
        if not check.get("passed"):
            severity = str(check.get("severity") or "error")
            add_gap(
                "validation_risks",
                f"check_failed:{check.get('name', 'unnamed')}",
                f"Validation check failed: {check.get('message') or check.get('name')}.",
                "blocking" if severity == "error" else "warning",
                ("internal_judgment", "presentation", "paper_external_claim"),
            )

    if not metrics.get("solver") and not result.get("status"):
        add_gap(
            "model_solver_software",
            "solver_identity_missing",
            "Solver identity or run status is missing.",
            "warning",
            ("internal_judgment", "presentation", "paper_external_claim"),
        )
    if not _software_version_evidence(result, metrics, artifact_items):
        add_gap(
            "model_solver_software",
            "software_versions_missing",
            "Software versions are not captured. Run doctor/version capture before claims beyond internal screening.",
            "warning",
            ("presentation", "paper_external_claim"),
        )
    if not _has_log_artifact(artifact_items):
        add_gap(
            "reproducibility_index",
            "solver_log_missing",
            "No solver or batch log artifact is indexed.",
            "warning",
            ("presentation", "paper_external_claim"),
        )
    if not artifact_items:
        add_gap(
            "reproducibility_index",
            "artifact_index_empty",
            "No source artifacts were available for the report index.",
            "blocking",
            ("internal_judgment", "presentation", "paper_external_claim"),
        )

    for section_id, title in REPORT_SECTIONS:
        section_gaps = [gap for gap in gaps if gap["section"] == section_id]
        status = "complete"
        if any(gap["severity"] == "blocking" for gap in section_gaps):
            status = "missing"
        elif section_gaps:
            status = "partial"
        sections.append(
            {
                "id": section_id,
                "title": title,
                "status": status,
                "gap_ids": [gap["id"] for gap in section_gaps],
            }
        )
    return sections, gaps


def _render_markdown_report(
    *,
    generated_at: str,
    work_order: dict[str, Any],
    result: dict[str, Any],
    spec: dict[str, Any],
    metrics: dict[str, Any],
    checks: list[dict[str, Any]],
    visualization_manifest: dict[str, Any],
    artifact_items: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    report_modes: dict[str, Any],
    summary: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append("# Thermal Simulation Report")
    lines.append("")
    lines.append(f"Generated at UTC: {generated_at}")
    lines.append("")
    lines.append("## Report Mode Boundary")
    for mode_id, mode in report_modes.items():
        supported = "supported" if mode["supported"] else "not ready"
        lines.append(f"- {mode['label']}: {supported}. {mode['boundary']}")
    lines.append("")

    lines.append("## Summary and Conclusion Boundary")
    lines.append(f"- Run status: {result.get('status', 'unknown')}")
    lines.append(f"- Validation status: {'passed' if result.get('passed') else 'not passed or incomplete'}")
    lines.append(f"- Conclusion: {summary['conclusion']}")
    if metrics:
        max_temp = metrics.get("max_temperature_C")
        if max_temp is not None:
            lines.append(f"- Max temperature: {max_temp} degC")
        if metrics.get("temperature_rise_K") is not None:
            lines.append(f"- Temperature rise: {metrics['temperature_rise_K']} K")
    lines.append("- Boundary: This report records available evidence only; missing items below are not inferred.")
    lines.append("")

    lines.append("## User Goal and Criteria")
    lines.append(f"- Goal: {_goal_text(work_order, spec)}")
    lines.append(f"- User job: {work_order.get('user_job', 'not supplied')}")
    lines.append(f"- Evidence level: {work_order.get('evidence_level', 'not supplied')}")
    lines.append(f"- Decision criterion: {_decision_criterion(work_order)}")
    lines.append("")

    lines.append("## Inputs, Assumptions, Materials, Heat Sources, and Boundaries")
    lines.append("### Parameters")
    parameter_rows = _parameters(spec)
    if parameter_rows:
        lines.extend(_markdown_table(["name", "value", "unit", "source"], parameter_rows))
    else:
        lines.append("- No simulation parameters were supplied.")
    lines.append("")
    assumptions = _assumptions(work_order, spec)
    lines.append("### Assumptions")
    if assumptions:
        for assumption in assumptions:
            lines.append(f"- {assumption}")
    else:
        lines.append("- No assumptions were recorded.")
    context = work_order.get("thick_context") if isinstance(work_order.get("thick_context"), dict) else {}
    lines.append("")
    lines.append("### User-Provided Physical Context")
    for key in ("system_description", "geometry", "materials", "heat_sources", "cooling_boundaries"):
        value = context.get(key)
        lines.append(f"- {key}: {value if value not in (None, '', [], {}) else 'missing'}")
    lines.append("")

    lines.append("## Model, Solver, and Software Versions")
    lines.append(f"- Backend: {spec.get('backend', 'unknown')}")
    lines.append(f"- Template id: {spec.get('template_id', 'unknown')}")
    lines.append(f"- Template path: {spec.get('template_path') or 'not supplied'}")
    lines.append(f"- Study type: {spec.get('study_type', 'unknown')}")
    lines.append(f"- Solver: {metrics.get('solver') or 'not supplied'}")
    lines.append(f"- Software versions: {_software_version_text(result, metrics)}")
    if metrics.get("command"):
        lines.append(f"- Solver command: `{metrics['command']}`")
    lines.append("")

    lines.append("## Result Figures and Numeric Tables")
    if metrics:
        rows = [[key, value] for key, value in sorted(metrics.items()) if _is_scalar(value)]
        lines.extend(_markdown_table(["metric", "value"], rows))
    else:
        lines.append("- No numeric metrics were supplied.")
    lines.append("")
    vis_items = _visualization_items(visualization_manifest)
    if vis_items:
        lines.append("### Visual Evidence")
        for item in vis_items:
            lines.append(f"- {item.get('id', item.get('role', 'visual'))}: {item.get('path') or item.get('description')}")
    else:
        lines.append("### Visual Evidence")
        lines.append("- Missing: no visualization manifest or figure artifacts were supplied.")
    lines.append("")

    lines.append("## Validation Status and Risks")
    if checks:
        lines.extend(
            _markdown_table(
                ["check", "passed", "severity", "message"],
                [[check.get("name"), check.get("passed"), check.get("severity", "error"), check.get("message")] for check in checks],
            )
        )
    else:
        lines.append("- No validation checks were supplied.")
    lines.append("")
    if gaps:
        lines.append("### Evidence Gaps")
        for gap in gaps:
            lines.append(f"- [{gap['severity']}] {gap['id']}: {gap['message']}")
    else:
        lines.append("### Evidence Gaps")
        lines.append("- None recorded.")
    lines.append("")

    lines.append("## File, Log, and Reproducibility Index")
    if artifact_items:
        rows = [
            [item.get("id"), item.get("role"), item.get("path"), item.get("exists"), item.get("sha256") or ""]
            for item in artifact_items
        ]
        lines.extend(_markdown_table(["id", "role", "path", "exists", "sha256"], rows))
    else:
        lines.append("- No source artifacts were indexed.")
    lines.append("")

    lines.append("## Manifest Completeness")
    lines.extend(
        _markdown_table(
            ["section", "status", "gap_ids"],
            [[section["title"], section["status"], ", ".join(section["gap_ids"])] for section in sections],
        )
    )
    lines.append("")
    return "\n".join(lines)


def _summary_data(
    work_order: dict[str, Any],
    result: dict[str, Any],
    spec: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    max_temp = _float_or_none(metrics.get("max_temperature_C"))
    threshold = _extract_temperature_threshold(_decision_criterion(work_order))
    if max_temp is None:
        conclusion = "No maximum-temperature metric is available, so no thermal conclusion can be stated."
        criterion_status = "not_evaluated"
    elif threshold is None:
        conclusion = f"Maximum temperature is {max_temp:g} degC, but no explicit acceptance threshold was recorded."
        criterion_status = "threshold_missing"
    elif max_temp <= threshold:
        conclusion = f"Maximum temperature is {max_temp:g} degC, within the recorded {threshold:g} degC criterion."
        criterion_status = "meets_recorded_criterion"
    else:
        conclusion = f"Maximum temperature is {max_temp:g} degC, exceeding the recorded {threshold:g} degC criterion."
        criterion_status = "violates_recorded_criterion"

    return {
        "goal": _goal_text(work_order, spec),
        "status": result.get("status", "unknown"),
        "passed": bool(result.get("passed")),
        "max_temperature_C": max_temp,
        "criterion_temperature_C": threshold,
        "criterion_status": criterion_status,
        "conclusion": conclusion,
    }


def _report_modes(
    result: dict[str, Any],
    checks: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    visualization_manifest: dict[str, Any],
) -> dict[str, Any]:
    error_checks_passed = _checks_passed(checks)
    blocking_gaps = [gap for gap in gaps if gap["severity"] == "blocking"]
    has_visuals = bool(_visualization_items(visualization_manifest))
    return {
        "internal_judgment": {
            "label": "Internal judgment",
            "supported": bool(result) and error_checks_passed,
            "boundary": "Suitable for first-pass reasoning only when assumptions and gaps are reviewed.",
        },
        "presentation": {
            "label": "Presentation",
            "supported": bool(result) and error_checks_passed and has_visuals and not blocking_gaps,
            "boundary": "Requires auditable figures, explicit criteria, and no blocking evidence gaps.",
        },
        "paper_external_claim": {
            "label": "Paper / External Claim",
            "supported": False,
            "boundary": "Requires independent validation, software/version capture, mesh or sensitivity evidence, and reviewed source data.",
        },
    }


def _collect_source_artifacts(
    *,
    output_dir: Path,
    result_data: dict[str, Any],
    visualization_manifest: dict[str, Any],
    external_artifacts: dict[str, str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    artifacts = result_data.get("artifacts") if isinstance(result_data.get("artifacts"), dict) else {}
    for artifact_id, raw_path in artifacts.items():
        if artifact_id in GENERATED_REPORT_ARTIFACT_KEYS:
            continue
        item = _artifact_item(str(artifact_id), "thermal_result_artifact", raw_path, output_dir)
        key = (item["id"], item["path"])
        if key not in seen:
            items.append(item)
            seen.add(key)

    for artifact_id, raw_path in external_artifacts.items():
        item = _artifact_item(str(artifact_id), _external_artifact_role(str(artifact_id)), raw_path, output_dir)
        key = (item["id"], item["path"])
        if key not in seen:
            items.append(item)
            seen.add(key)

    for item in _iter_visualization_artifacts(visualization_manifest):
        artifact = _artifact_item(item["id"], item["role"], item["path"], output_dir, metadata=item.get("metadata", {}))
        key = (artifact["id"], artifact["path"])
        if key not in seen:
            items.append(artifact)
            seen.add(key)

    return items


def _artifact_item(
    artifact_id: str,
    role: str,
    raw_path: Any,
    base_dir: Path,
    *,
    metadata: dict[str, Any] | None = None,
    self_reference: bool = False,
) -> dict[str, Any]:
    path = _path_from(raw_path, base_dir)
    exists = path.exists()
    is_file = exists and path.is_file()
    item = {
        "id": artifact_id,
        "role": role,
        "path": str(path),
        "exists": exists,
        "size_bytes": path.stat().st_size if is_file else None,
        "sha256": None if self_reference or not is_file else _sha256(path),
    }
    if self_reference:
        item["note"] = "Self-reference; hash omitted."
    if metadata:
        item["metadata"] = metadata
    return item


def _iter_visualization_artifacts(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if not manifest:
        return []
    artifacts: list[dict[str, Any]] = []
    for role in ("figures", "images", "tables", "animations", "artifacts", "logs"):
        value = manifest.get(role)
        if isinstance(value, dict):
            for key, path in value.items():
                artifacts.append({"id": str(key), "role": f"visualization_{role}", "path": path})
        elif isinstance(value, list):
            for index, item in enumerate(value, start=1):
                if isinstance(item, dict):
                    path = item.get("path") or item.get("file") or item.get("href")
                    if path:
                        artifact_id = str(item.get("id") or item.get("name") or f"{role}_{index}")
                        artifacts.append(
                            {
                                "id": artifact_id,
                                "role": f"visualization_{role}",
                                "path": path,
                                "metadata": {key: value for key, value in item.items() if key not in {"path", "file", "href"}},
                            }
                        )
                elif item:
                    artifacts.append({"id": f"{role}_{index}", "role": f"visualization_{role}", "path": item})
    return artifacts


def _visualization_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return _iter_visualization_artifacts(manifest)


def _to_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        data = to_dict()
        return data if isinstance(data, dict) else {}
    return {}


def _checks_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    checks = result.get("checks")
    if not isinstance(checks, list):
        return []
    return [_check_to_dict(check) for check in checks]


def _check_to_dict(check: CheckResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(check, CheckResult):
        return check.to_dict()
    if isinstance(check, dict):
        return {
            "name": str(check.get("name") or "unnamed_check"),
            "passed": bool(check.get("passed")),
            "message": str(check.get("message") or ""),
            "severity": str(check.get("severity") or "error"),
        }
    return {
        "name": "unknown_check",
        "passed": False,
        "message": f"Unsupported check type: {type(check).__name__}",
        "severity": "error",
    }


def _deduplicate_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for check in checks:
        key = (str(check.get("name")), str(check.get("message")))
        if key in seen:
            continue
        deduped.append(check)
        seen.add(key)
    return deduped


def _input_status(present: bool, label: str) -> dict[str, str]:
    return {
        "status": "complete" if present else "missing",
        "message": f"{label} supplied." if present else f"{label} not supplied.",
    }


def _checks_passed(checks: list[dict[str, Any]]) -> bool:
    return bool(checks) and all(bool(check.get("passed")) for check in checks if str(check.get("severity") or "error") == "error")


def _goal_text(work_order: dict[str, Any], spec: dict[str, Any]) -> str:
    return str(work_order.get("raw_goal") or spec.get("source_request") or "not supplied")


def _decision_criterion(work_order: dict[str, Any]) -> str:
    core_thread = work_order.get("core_thread") if isinstance(work_order.get("core_thread"), dict) else {}
    return str(core_thread.get("decision_criterion") or "not_declared")


def _parameters(spec: dict[str, Any]) -> list[list[Any]]:
    parameters = spec.get("parameters")
    if not isinstance(parameters, list):
        return []
    rows: list[list[Any]] = []
    for parameter in parameters:
        if not isinstance(parameter, dict):
            continue
        rows.append(
            [
                parameter.get("name"),
                parameter.get("value"),
                parameter.get("unit"),
                parameter.get("source"),
            ]
        )
    return rows


def _assumptions(work_order: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    assumptions: list[str] = []
    for source in (work_order.get("assumptions"), spec.get("assumptions")):
        if isinstance(source, list):
            assumptions.extend(str(item) for item in source if item not in (None, ""))
    return assumptions


def _parameter_named(spec: dict[str, Any], name: str) -> bool:
    for parameter in spec.get("parameters", []):
        if isinstance(parameter, dict) and parameter.get("name") == name:
            return True
    return False


def _has_summary_table(artifact_items: list[dict[str, Any]]) -> bool:
    return any("summary" in str(item.get("id", "")).lower() and str(item.get("path", "")).lower().endswith(".csv") for item in artifact_items)


def _has_log_artifact(artifact_items: list[dict[str, Any]]) -> bool:
    return any("log" in str(item.get("id", "")).lower() or str(item.get("path", "")).lower().endswith(".log") for item in artifact_items)


def _has_comsol_or_origin_artifacts(artifact_items: list[dict[str, Any]]) -> bool:
    return any(
        "comsol" in str(item.get("id", "")).lower()
        or "origin" in str(item.get("id", "")).lower()
        or str(item.get("path", "")).lower().endswith((".mph", ".opju"))
        for item in artifact_items
    )


def _software_version_evidence(result: dict[str, Any], metrics: dict[str, Any], artifact_items: list[dict[str, Any]]) -> bool:
    if result.get("software_versions") or metrics.get("software_versions") or metrics.get("software_version"):
        return True
    return any("doctor" in str(item.get("id", "")).lower() or "version" in str(item.get("id", "")).lower() for item in artifact_items)


def _software_version_text(result: dict[str, Any], metrics: dict[str, Any]) -> str:
    value = result.get("software_versions") or metrics.get("software_versions") or metrics.get("software_version")
    if value:
        return str(value)
    return "missing"


def _external_artifact_role(artifact_id: str) -> str:
    lowered = artifact_id.lower()
    if "comsol" in lowered or lowered.endswith("_mph") or lowered.endswith("_log"):
        return "comsol_artifact"
    if "origin" in lowered or lowered.endswith("_opju"):
        return "origin_artifact"
    return "external_artifact"


def _path_from(raw_path: Any, base_dir: Path) -> Path:
    path = raw_path if isinstance(raw_path, Path) else Path(str(raw_path))
    if not path.is_absolute():
        path = base_dir / path
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_temperature_threshold(text: str) -> float | None:
    if not text:
        return None
    normalized = text.lower()
    matches = re.findall(r"(-?\d+(?:\.\d+)?)\s*(?:degc|degree c|degrees c|c\b)", normalized)
    if matches:
        return float(matches[-1])
    matches = re.findall(r"(?:below|under|less than|not exceed|<=|<)\s*(-?\d+(?:\.\d+)?)", normalized)
    if matches:
        return float(matches[-1])
    return None


def _float_or_none(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        output.append("| " + " | ".join(_markdown_cell(item) for item in row) + " |")
    return output


def _markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _markdown_to_simple_html(markdown_text: str) -> str:
    body = "\n".join(f"<pre>{html.escape(line)}</pre>" for line in markdown_text.splitlines())
    return f"<!doctype html><html><head><meta charset=\"utf-8\"><title>Thermal Simulation Report</title></head><body>{body}</body></html>"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

