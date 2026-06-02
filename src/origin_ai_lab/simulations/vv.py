from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from origin_ai_lab.models import CheckResult, ThermalSimulationSpec


PUBLICATION_EVIDENCE_LEVEL = "publication_or_external_claim"


@dataclass(frozen=True)
class SolverIterationRecord:
    line_number: int
    raw: str
    iteration: int | None = None
    residual: float | None = None
    residual_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_number": self.line_number,
            "iteration": self.iteration,
            "residual": self.residual,
            "residual_name": self.residual_name,
            "raw": self.raw,
        }


@dataclass(frozen=True)
class SolverLogSummary:
    status: str
    completed: bool
    completion_percent: float | None = None
    runtime_seconds: float | None = None
    warning_count: int = 0
    warnings: tuple[str, ...] = ()
    error_count: int = 0
    errors: tuple[str, ...] = ()
    iterations: tuple[SolverIterationRecord, ...] = ()
    return_code: int | None = None
    line_count: int = 0
    tail: tuple[str, ...] = ()
    schema_version: str = "solver-log-summary/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "completed": self.completed,
            "completion_percent": self.completion_percent,
            "runtime_seconds": self.runtime_seconds,
            "warning_count": self.warning_count,
            "warnings": list(self.warnings),
            "error_count": self.error_count,
            "errors": list(self.errors),
            "iterations": [item.to_dict() for item in self.iterations],
            "return_code": self.return_code,
            "line_count": self.line_count,
            "tail": list(self.tail),
        }


@dataclass(frozen=True)
class BoundaryConditionAuditEntry:
    item_id: str
    item_type: str
    role: str
    target: str | None
    required_fields: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    value_fields: dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    status: str = "needs_review"
    risks: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type,
            "role": self.role,
            "target": self.target,
            "required_fields": list(self.required_fields),
            "missing_fields": list(self.missing_fields),
            "value_fields": self.value_fields,
            "source": self.source,
            "status": self.status,
            "risks": list(self.risks),
        }


@dataclass(frozen=True)
class BoundaryConditionAudit:
    entries: tuple[BoundaryConditionAuditEntry, ...]
    status: str
    completeness_score: float
    has_heat_input: bool
    has_heat_sink_or_reference: bool
    risks: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    schema_version: str = "boundary-condition-audit/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "completeness_score": self.completeness_score,
            "has_heat_input": self.has_heat_input,
            "has_heat_sink_or_reference": self.has_heat_sink_or_reference,
            "risks": list(self.risks),
            "gaps": list(self.gaps),
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class EnergyBalanceTerm:
    term_id: str
    role: str
    value_W: float | None
    source: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "term_id": self.term_id,
            "role": self.role,
            "value_W": self.value_W,
            "source": self.source,
        }


@dataclass(frozen=True)
class EnergyBalanceCheck:
    status: str
    passed: bool
    tolerance_percent: float
    residual_W: float | None = None
    residual_percent: float | None = None
    terms: tuple[EnergyBalanceTerm, ...] = ()
    gaps: tuple[str, ...] = ()
    schema_version: str = "energy-balance-check/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "passed": self.passed,
            "tolerance_percent": self.tolerance_percent,
            "residual_W": self.residual_W,
            "residual_percent": self.residual_percent,
            "terms": [term.to_dict() for term in self.terms],
            "gaps": list(self.gaps),
        }


@dataclass(frozen=True)
class ConvergenceStudyPoint:
    point_id: str
    kind: str
    mesh_policy: str | None = None
    time_step_s: float | None = None
    parameters: dict[str, float] = field(default_factory=dict)
    status: str = "planned"
    result_path: str | None = None
    qoi_metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "point_id": self.point_id,
            "kind": self.kind,
            "mesh_policy": self.mesh_policy,
            "time_step_s": self.time_step_s,
            "parameters": self.parameters,
            "status": self.status,
            "result_path": self.result_path,
            "qoi_metrics": self.qoi_metrics,
        }


@dataclass(frozen=True)
class ConvergenceStudyPlan:
    template_id: str
    study_type: str
    evidence_level: str
    points: tuple[ConvergenceStudyPoint, ...]
    qoi_names: tuple[str, ...]
    acceptance: dict[str, Any]
    automation_status: str = "interface_only"
    schema_version: str = "thermal-convergence-study-plan/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "template_id": self.template_id,
            "study_type": self.study_type,
            "evidence_level": self.evidence_level,
            "automation_status": self.automation_status,
            "qoi_names": list(self.qoi_names),
            "acceptance": self.acceptance,
            "points": [point.to_dict() for point in self.points],
            "runner_interface": {
                "entrypoint": "future:run_convergence_study(plan, output_dir)",
                "input_contract": "thermal-convergence-study-plan/v1",
                "output_contract": "thermal-convergence-study-result/v1",
                "note": "The first version records the interface and planned points; automatic COMSOL reruns are not enabled yet.",
            },
        }


@dataclass(frozen=True)
class CredibilityCard:
    evidence_level: str
    credibility_status: str
    input_completeness: dict[str, Any]
    validation_status: dict[str, Any]
    required_evidence: tuple[dict[str, Any], ...]
    risks: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    artifacts: dict[str, str] = field(default_factory=dict)
    schema_version: str = "thermal-credibility-card/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evidence_level": self.evidence_level,
            "credibility_status": self.credibility_status,
            "input_completeness": self.input_completeness,
            "validation_status": self.validation_status,
            "required_evidence": list(self.required_evidence),
            "risks": list(self.risks),
            "gaps": list(self.gaps),
            "artifacts": self.artifacts,
        }


_COMPLETION_RE = re.compile(r"(?P<percent>\d{1,3}(?:\.\d+)?)\s*%")
_ITER_RE = re.compile(r"\biter(?:ation)?(?:\s+no\.?)?\s*[:=#]?\s*(?P<iteration>\d+)\b", re.IGNORECASE)
_RESIDUAL_RE = re.compile(
    r"\b(?P<name>(?:relative\s+)?(?:residual|res))\b\s*[:=]?\s*(?P<value>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)",
    re.IGNORECASE,
)
_RUNTIME_LINE_RE = re.compile(
    r"(?:\b(?:total\s+)?(?:elapsed|run|running|solution|solver|wall)\s+time\b\s*(?:[:=]|is)?|"
    r"(?:\u8fd0\u884c\u65f6\u95f4|\u603b\u65f6\u95f4|\u6c42\u89e3\u65f6\u95f4|\u4fdd\u5b58\u65f6\u95f4)\s*[:\uff1a])"
    r"\s*(?P<value>.+)$",
    re.IGNORECASE,
)
_FINISHED_IN_RE = re.compile(r"\bfinished\s+in\s+(?P<value>.+)$", re.IGNORECASE)


def parse_comsol_solver_log(log_text: str, return_code: int | None = None) -> SolverLogSummary:
    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    warnings: list[str] = []
    errors: list[str] = []
    iterations: list[SolverIterationRecord] = []
    completion_values: list[float] = []
    runtime_seconds: float | None = None

    for line_number, line in enumerate(lines, start=1):
        lower = line.lower()
        completion_values.extend(_completion_values(line))
        if _is_warning_line(lower):
            warnings.append(line)
        if _is_error_line(lower):
            errors.append(line)
        runtime_seconds = _latest_runtime(runtime_seconds, line)
        iteration = _iteration_record(line_number, line)
        if iteration is not None:
            iterations.append(iteration)

    completion_percent = max(completion_values) if completion_values else None
    failed = (return_code is not None and return_code != 0) or bool(errors)
    completed = _log_completed(log_text, completion_percent, return_code, failed)
    if failed:
        status = "failed"
    elif completed and warnings:
        status = "complete_with_warnings"
    elif completed:
        status = "complete"
    else:
        status = "unknown"

    return SolverLogSummary(
        status=status,
        completed=completed,
        completion_percent=completion_percent,
        runtime_seconds=runtime_seconds,
        warning_count=len(warnings),
        warnings=tuple(warnings[:20]),
        error_count=len(errors),
        errors=tuple(errors[:20]),
        iterations=tuple(iterations[-50:]),
        return_code=return_code,
        line_count=len(lines),
        tail=tuple(lines[-12:]),
    )


def build_boundary_condition_audit_from_proposal(proposal: dict[str, Any]) -> BoundaryConditionAudit:
    entries: list[BoundaryConditionAuditEntry] = []
    for source in _list_of_dicts(proposal.get("heat_sources")):
        entries.append(_audit_entry(source, source_kind="heat_source", source_label="proposal"))
    for boundary in _list_of_dicts(proposal.get("boundary_conditions")):
        entries.append(_audit_entry(boundary, source_kind="boundary_condition", source_label="proposal"))
    return _boundary_audit_from_entries(entries)


def build_boundary_condition_audit_from_spec(spec: ThermalSimulationSpec) -> BoundaryConditionAudit:
    values = spec.parameter_map()
    entries: list[BoundaryConditionAuditEntry] = []
    if "chip_power_W" in values:
        entries.append(
            BoundaryConditionAuditEntry(
                item_id="chip_power_W",
                item_type="total_power",
                role="heat_input",
                target="template_defined_heat_source" if spec.template_path else "mock_lumped_chip",
                required_fields=("value_W", "target"),
                value_fields={"value_W": values["chip_power_W"]},
                source=_parameter_source(spec, "chip_power_W"),
                status="needs_review" if spec.template_path else "declared",
                risks=(_template_or_mock_heat_source_risk(spec),),
            )
        )
    boundary_missing = [name for name in ("h_conv_W_m2K", "ambient_temp_C") if name not in values]
    entries.append(
        BoundaryConditionAuditEntry(
            item_id="ambient_convection",
            item_type="convection",
            role="heat_sink_or_reference",
            target="template_defined_exterior_surfaces" if spec.template_path else "mock_cooling_area",
            required_fields=("h_W_m2K", "ambient_temp_C", "target"),
            missing_fields=tuple("h_W_m2K" if name == "h_conv_W_m2K" else name for name in boundary_missing),
            value_fields={
                key: value
                for key, value in {
                    "h_W_m2K": values.get("h_conv_W_m2K"),
                    "ambient_temp_C": values.get("ambient_temp_C"),
                    "cooling_area_m2": values.get("cooling_area_m2"),
                }.items()
                if value is not None
            },
            source="thermal_simulation_spec",
            status="needs_review" if spec.template_path else ("declared" if not boundary_missing else "incomplete"),
            risks=(_template_or_mock_boundary_risk(spec),),
        )
    )
    return _boundary_audit_from_entries(entries)


def build_energy_balance_check(metrics: dict[str, Any], tolerance_percent: float = 5.0) -> EnergyBalanceCheck:
    terms: list[EnergyBalanceTerm] = []
    input_w = _number_from(
        metrics.get("heat_input_W")
        if metrics.get("heat_input_W") is not None
        else metrics.get("chip_power_W")
    )
    output_w = _number_from(
        metrics.get("heat_output_W")
        if metrics.get("heat_output_W") is not None
        else metrics.get("convective_heat_loss_W")
    )
    residual_percent = _number_from(metrics.get("energy_balance_error_percent"))
    residual_w = _number_from(metrics.get("energy_balance_residual_W"))

    if input_w is not None:
        terms.append(EnergyBalanceTerm("declared_heat_input", "input", input_w, "metrics"))
    if output_w is not None:
        terms.append(EnergyBalanceTerm("reported_heat_output", "output", output_w, "metrics"))
    if residual_w is None and input_w is not None and output_w is not None:
        residual_w = input_w - output_w
    if residual_percent is None and residual_w is not None and input_w not in (None, 0.0):
        residual_percent = abs(residual_w) / abs(input_w) * 100.0

    gaps: list[str] = []
    if input_w is None:
        gaps.append("No heat-input power was reported.")
    if output_w is None and residual_percent is None:
        gaps.append("No heat-output or explicit energy-balance residual was reported.")

    if residual_percent is None:
        return EnergyBalanceCheck(
            status="not_available",
            passed=False,
            tolerance_percent=tolerance_percent,
            residual_W=residual_w,
            residual_percent=None,
            terms=tuple(terms),
            gaps=tuple(gaps),
        )

    passed = abs(residual_percent) <= tolerance_percent
    return EnergyBalanceCheck(
        status="passed" if passed else "failed",
        passed=passed,
        tolerance_percent=tolerance_percent,
        residual_W=residual_w,
        residual_percent=round(residual_percent, 6),
        terms=tuple(terms),
        gaps=tuple(gaps),
    )


def evaluate_energy_balance_check(energy_balance: EnergyBalanceCheck, evidence_level: str) -> CheckResult:
    if energy_balance.passed:
        return CheckResult(
            name="thermal_energy_balance",
            passed=True,
            message=f"Energy-balance residual is {energy_balance.residual_percent:g}%."
            if energy_balance.residual_percent is not None
            else "Energy-balance check passed.",
        )
    if energy_balance.status == "not_available" and evidence_level != PUBLICATION_EVIDENCE_LEVEL:
        return CheckResult(
            name="thermal_energy_balance",
            passed=True,
            message="Energy-balance terms are not available for this backend yet.",
            severity="warning",
        )
    return CheckResult(
        name="thermal_energy_balance",
        passed=False,
        message="Energy-balance evidence is missing or outside tolerance.",
    )


def build_convergence_study_plan(
    spec: ThermalSimulationSpec,
    evidence_level: str | None = None,
    qoi_names: tuple[str, ...] | None = None,
) -> ConvergenceStudyPlan:
    level = evidence_level or infer_thermal_evidence_level(spec.source_request)
    qois = qoi_names or tuple(spec.outputs) or ("max_temperature_C",)
    points = [
        ConvergenceStudyPoint("mesh_coarse", "mesh", mesh_policy="physics_controlled_coarser"),
        ConvergenceStudyPoint("mesh_normal", "mesh", mesh_policy="physics_controlled_normal"),
        ConvergenceStudyPoint("mesh_fine", "mesh", mesh_policy="physics_controlled_finer"),
    ]
    if "time" in spec.study_type.lower() or "transient" in spec.study_type.lower():
        points.extend(
            [
                ConvergenceStudyPoint("time_step_large", "time_step", time_step_s=1.0),
                ConvergenceStudyPoint("time_step_medium", "time_step", time_step_s=0.5),
                ConvergenceStudyPoint("time_step_small", "time_step", time_step_s=0.25),
            ]
        )

    return ConvergenceStudyPlan(
        template_id=spec.template_id,
        study_type=spec.study_type,
        evidence_level=level,
        qoi_names=qois,
        points=tuple(points),
        acceptance={
            "qoi_relative_change_percent_max": 2.0 if level == PUBLICATION_EVIDENCE_LEVEL else 5.0,
            "energy_balance_residual_percent_max": 5.0,
            "minimum_mesh_levels": 3,
            "minimum_time_step_levels": 3 if any(point.kind == "time_step" for point in points) else 0,
        },
    )


def build_credibility_card(
    spec: ThermalSimulationSpec,
    checks: list[CheckResult],
    metrics: dict[str, Any],
    artifacts: dict[str, str],
    boundary_audit: BoundaryConditionAudit,
    energy_balance: EnergyBalanceCheck,
    solver_log_summary: SolverLogSummary | dict[str, Any] | None = None,
    convergence_plan: ConvergenceStudyPlan | None = None,
    evidence_level: str | None = None,
) -> CredibilityCard:
    level = evidence_level or infer_thermal_evidence_level(spec.source_request)
    required = _required_evidence(level, metrics, boundary_audit, energy_balance, solver_log_summary, convergence_plan)
    failed_error_checks = [check for check in checks if check.severity == "error" and not check.passed]
    gaps = _credibility_gaps(spec, level, required, metrics, boundary_audit, energy_balance)
    risks = _credibility_risks(checks, boundary_audit, solver_log_summary)
    status = _credibility_status(level, failed_error_checks, gaps, energy_balance)

    return CredibilityCard(
        evidence_level=level,
        credibility_status=status,
        input_completeness=_input_completeness(spec, boundary_audit),
        validation_status={
            "solver_converged": bool(metrics.get("solver_converged")),
            "error_checks_passed": not failed_error_checks,
            "boundary_audit": boundary_audit.status,
            "energy_balance": energy_balance.status,
            "convergence": "planned_only" if convergence_plan is not None else "not_planned",
            "solver_log": _solver_log_status(solver_log_summary),
        },
        required_evidence=tuple(required),
        risks=tuple(risks),
        gaps=tuple(gaps),
        artifacts=dict(artifacts),
    )


def infer_thermal_evidence_level(request_text: str, requested_level: str | None = None) -> str:
    if requested_level and requested_level != "auto":
        return requested_level
    text = request_text.lower()
    publication_keywords = (
        "paper",
        "publication",
        "manuscript",
        "external",
        "validation",
        "benchmark",
        "review",
        "credible",
        "\u8bba\u6587",
        "\u5bf9\u5916",
        "\u9a8c\u8bc1",
        "\u5ba1\u7a3f",
        "\u53ef\u4fe1",
    )
    if any(keyword in text for keyword in publication_keywords):
        return PUBLICATION_EVIDENCE_LEVEL
    if any(keyword in text for keyword in ("report", "presentation", "\u6c47\u62a5", "\u5c55\u793a")):
        return "decision_support"
    if any(keyword in text for keyword in ("estimate", "screen", "\u5224\u65ad", "\u4f30\u7b97")):
        return "quick_screening"
    return "scoping"


def _completion_values(line: str) -> list[float]:
    values: list[float] = []
    for match in _COMPLETION_RE.finditer(line):
        try:
            percent = float(match.group("percent"))
        except ValueError:
            continue
        if 0.0 <= percent <= 100.0:
            values.append(percent)
    return values


def _is_warning_line(lower_line: str) -> bool:
    return "warning" in lower_line or lower_line.startswith("warn") or "\u8b66\u544a" in lower_line


def _is_error_line(lower_line: str) -> bool:
    if "error estimate" in lower_line or "relative error" in lower_line:
        return False
    return (
        lower_line.startswith("error")
        or " error:" in lower_line
        or "failed" in lower_line
        or "exception" in lower_line
        or "\u9519\u8bef" in lower_line
        or "\u5931\u8d25" in lower_line
    )


def _latest_runtime(previous: float | None, line: str) -> float | None:
    match = _RUNTIME_LINE_RE.search(line) or _FINISHED_IN_RE.search(line)
    if not match:
        return previous
    parsed = _parse_duration_seconds(match.group("value"))
    return parsed if parsed is not None else previous


def _iteration_record(line_number: int, line: str) -> SolverIterationRecord | None:
    if "iter" not in line.lower() and "res" not in line.lower():
        return None
    iteration_match = _ITER_RE.search(line)
    residual_match = _RESIDUAL_RE.search(line)
    if iteration_match is None and residual_match is None:
        return None
    iteration = int(iteration_match.group("iteration")) if iteration_match else None
    residual = None
    residual_name = None
    if residual_match:
        residual_name = residual_match.group("name").strip().lower()
        try:
            residual = float(residual_match.group("value"))
        except ValueError:
            residual = None
    return SolverIterationRecord(
        line_number=line_number,
        raw=line,
        iteration=iteration,
        residual=residual,
        residual_name=residual_name,
    )


def _parse_duration_seconds(value: str) -> float | None:
    cleaned = value.strip().rstrip(".\u3002")
    clock_match = re.search(r"\b(?:(?P<hours>\d+):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{1,2}(?:\.\d+)?)\b", cleaned)
    if clock_match:
        hours = float(clock_match.group("hours") or 0)
        minutes = float(clock_match.group("minutes") or 0)
        seconds = float(clock_match.group("seconds") or 0)
        return hours * 3600.0 + minutes * 60.0 + seconds

    total = 0.0
    for number, unit in re.findall(
        r"([-+]?\d*\.?\d+)\s*(hours?|hrs?|h|minutes?|mins?|min|seconds?|secs?|s)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        amount = float(number)
        unit_lower = unit.lower()
        if unit_lower.startswith("h"):
            total += amount * 3600.0
        elif unit_lower.startswith("min"):
            total += amount * 60.0
        else:
            total += amount
    return total if total > 0.0 else None


def _log_completed(log_text: str, completion_percent: float | None, return_code: int | None, failed: bool) -> bool:
    if failed:
        return False
    lower = log_text.lower()
    if completion_percent is not None and completion_percent >= 100.0:
        return True
    if re.search(r"\b(completed|finished|done)\b", lower):
        return True
    if "\u5b8c\u6210" in log_text:
        return True
    if return_code == 0 and not log_text.strip():
        return True
    return return_code == 0 and ("saving model" in lower or "solution time" in lower)


def _audit_entry(item: dict[str, Any], source_kind: str, source_label: str) -> BoundaryConditionAuditEntry:
    item_id = str(item.get("id") or source_kind)
    item_type = str(item.get("type") or "unknown")
    target = _optional_str(item.get("target"))
    required = _required_fields_for_item(item_type, source_kind)
    missing = tuple(field for field in required if _field_missing(item, field))
    risks = list(_risks_for_item(item_type, target, missing, source_kind))
    status = "declared" if not missing and not risks else "incomplete" if missing else "needs_review"
    return BoundaryConditionAuditEntry(
        item_id=item_id,
        item_type=item_type,
        role=_role_for_item(item_type, source_kind),
        target=target,
        required_fields=required,
        missing_fields=missing,
        value_fields={key: item[key] for key in sorted(item) if key not in {"id", "type", "target"}},
        source=source_label,
        status=status,
        risks=tuple(risks),
    )


def _boundary_audit_from_entries(entries: list[BoundaryConditionAuditEntry]) -> BoundaryConditionAudit:
    has_heat_input = any(entry.role == "heat_input" for entry in entries)
    has_sink = any(entry.role == "heat_sink_or_reference" for entry in entries)
    all_required = sum(len(entry.required_fields) for entry in entries)
    missing_required = sum(len(entry.missing_fields) for entry in entries)
    completeness = 0.0 if all_required == 0 else round(max(0.0, 1.0 - missing_required / all_required), 3)
    risks = [risk for entry in entries for risk in entry.risks]
    gaps: list[str] = []
    if not has_heat_input:
        gaps.append("No declared heat input was found.")
    if not has_sink:
        gaps.append("No heat sink or reference temperature boundary was found.")
    gaps.extend(
        f"{entry.item_id} is missing {', '.join(entry.missing_fields)}."
        for entry in entries
        if entry.missing_fields
    )
    if gaps:
        status = "incomplete"
    elif risks:
        status = "needs_review"
    else:
        status = "complete"
    return BoundaryConditionAudit(
        entries=tuple(entries),
        status=status,
        completeness_score=completeness,
        has_heat_input=has_heat_input,
        has_heat_sink_or_reference=has_sink,
        risks=tuple(risks),
        gaps=tuple(gaps),
    )


def _required_fields_for_item(item_type: str, source_kind: str) -> tuple[str, ...]:
    if source_kind == "heat_source":
        return {
            "total_power": ("target", "value_W"),
            "volumetric_heat": ("target", "value_W_m3"),
            "boundary_heat_flux": ("target", "value_W_m2"),
        }.get(item_type, ("target",))
    return {
        "convection": ("target", "h_W_m2K", "ambient_temp_C"),
        "fixed_temperature": ("target", "temperature_C"),
        "heat_flux": ("target", "value_W_m2"),
        "insulation": ("target",),
        "symmetry": ("target",),
    }.get(item_type, ("target",))


def _field_missing(item: dict[str, Any], field: str) -> bool:
    if field == "temperature_C":
        return _number_from(item.get("temperature_C", item.get("value_C"))) is None
    if field == "target":
        return not _optional_str(item.get("target"))
    value = item.get(field)
    if field.startswith("value") or field.startswith("h_") or field.endswith("_C"):
        return _number_from(value) is None
    return value in (None, "", [], {})


def _risks_for_item(item_type: str, target: str | None, missing: tuple[str, ...], source_kind: str) -> tuple[str, ...]:
    risks: list[str] = []
    if item_type == "unknown":
        risks.append(f"Unsupported {source_kind} type.")
    if target and target in {"all", "all_surfaces", "all_domains"}:
        risks.append("Target is broad; confirm it does not include unintended faces or domains.")
    if source_kind == "boundary_condition" and item_type in {"insulation", "symmetry"}:
        risks.append("Adiabatic/symmetry boundaries are acceptable only when the physical symmetry or insulation is justified.")
    if missing:
        risks.append("Required boundary/load fields are missing.")
    return tuple(risks)


def _role_for_item(item_type: str, source_kind: str) -> str:
    if source_kind == "heat_source" or item_type in {"heat_flux", "boundary_heat_flux"}:
        return "heat_input"
    if item_type in {"convection", "fixed_temperature"}:
        return "heat_sink_or_reference"
    return "constraint_or_symmetry"


def _template_or_mock_heat_source_risk(spec: ThermalSimulationSpec) -> str:
    if spec.template_path:
        return "Actual heat-source domain is defined inside the template and has not been audited from COMSOL."
    return "Mock heat-source geometry is a lumped abstraction."


def _template_or_mock_boundary_risk(spec: ThermalSimulationSpec) -> str:
    if spec.template_path:
        return "Actual boundary selections are inside the template and require COMSOL/model audit."
    return "Mock convection area is a lumped effective area."


def _required_evidence(
    evidence_level: str,
    metrics: dict[str, Any],
    boundary_audit: BoundaryConditionAudit,
    energy_balance: EnergyBalanceCheck,
    solver_log_summary: SolverLogSummary | dict[str, Any] | None,
    convergence_plan: ConvergenceStudyPlan | None,
) -> list[dict[str, Any]]:
    items = [
        {
            "id": "declared_inputs",
            "required": True,
            "satisfied": boundary_audit.completeness_score >= 0.75,
            "status": boundary_audit.status,
        },
        {
            "id": "solver_status",
            "required": True,
            "satisfied": bool(metrics.get("solver_converged")) or _solver_log_completed(solver_log_summary),
            "status": _solver_log_status(solver_log_summary),
        },
        {
            "id": "energy_balance",
            "required": evidence_level != "quick_screening",
            "satisfied": energy_balance.passed,
            "status": energy_balance.status,
        },
    ]
    if evidence_level in {"decision_support", PUBLICATION_EVIDENCE_LEVEL}:
        items.append(
            {
                "id": "boundary_condition_audit",
                "required": True,
                "satisfied": boundary_audit.status in {"complete", "needs_review"},
                "status": boundary_audit.status,
            }
        )
    if evidence_level == PUBLICATION_EVIDENCE_LEVEL:
        items.extend(
            [
                {
                    "id": "official_golden_case_or_benchmark",
                    "required": True,
                    "satisfied": bool(metrics.get("golden_case_passed")),
                    "status": "passed" if metrics.get("golden_case_passed") else "missing",
                },
                {
                    "id": "mesh_or_time_convergence",
                    "required": True,
                    "satisfied": bool(metrics.get("convergence_passed")),
                    "status": "planned_only" if convergence_plan is not None else "missing",
                },
            ]
        )
    return items


def _credibility_gaps(
    spec: ThermalSimulationSpec,
    evidence_level: str,
    required: list[dict[str, Any]],
    metrics: dict[str, Any],
    boundary_audit: BoundaryConditionAudit,
    energy_balance: EnergyBalanceCheck,
) -> list[str]:
    gaps = list(boundary_audit.gaps)
    gaps.extend(energy_balance.gaps)
    defaulted = [parameter.name for parameter in spec.parameters if parameter.source == "default"]
    if defaulted:
        gaps.append(f"Defaulted inputs need review: {', '.join(defaulted)}.")
    if not metrics.get("solver_converged"):
        gaps.append("No converged solver result is recorded.")
    for item in required:
        if item.get("required") and not item.get("satisfied"):
            gaps.append(f"Required evidence is missing or incomplete: {item['id']}.")
    if evidence_level == PUBLICATION_EVIDENCE_LEVEL and "output_mph" not in metrics:
        gaps.append("Publication/external claims need raw solver artifacts and benchmark comparison, not only a mock result.")
    return _dedupe(gaps)


def _credibility_risks(
    checks: list[CheckResult],
    boundary_audit: BoundaryConditionAudit,
    solver_log_summary: SolverLogSummary | dict[str, Any] | None,
) -> list[str]:
    risks = list(boundary_audit.risks)
    risks.extend(check.message for check in checks if check.severity == "warning" and not check.passed)
    warnings = _solver_log_warnings(solver_log_summary)
    risks.extend(warnings)
    return _dedupe(risks)


def _credibility_status(
    evidence_level: str,
    failed_error_checks: list[CheckResult],
    gaps: list[str],
    energy_balance: EnergyBalanceCheck,
) -> str:
    if failed_error_checks:
        return "failed_checks"
    if evidence_level == PUBLICATION_EVIDENCE_LEVEL and gaps:
        return "insufficient_for_publication_or_external_claim"
    if energy_balance.status == "failed":
        return "needs_energy_balance_review"
    if gaps:
        return "usable_with_gaps"
    return "credible_for_declared_use"


def _input_completeness(spec: ThermalSimulationSpec, boundary_audit: BoundaryConditionAudit) -> dict[str, Any]:
    total = len(spec.parameters)
    user_supplied = [parameter.name for parameter in spec.parameters if parameter.source == "user"]
    defaulted = [parameter.name for parameter in spec.parameters if parameter.source == "default"]
    return {
        "score": round((len(user_supplied) / total if total else 0.0) * 0.6 + boundary_audit.completeness_score * 0.4, 3),
        "declared_parameter_count": total,
        "user_supplied_parameters": user_supplied,
        "defaulted_parameters": defaulted,
        "boundary_condition_audit_score": boundary_audit.completeness_score,
        "assumptions": list(spec.assumptions),
    }


def _solver_log_status(summary: SolverLogSummary | dict[str, Any] | None) -> str:
    if summary is None:
        return "not_available"
    if isinstance(summary, SolverLogSummary):
        return summary.status
    return str(summary.get("status") or "not_available")


def _solver_log_completed(summary: SolverLogSummary | dict[str, Any] | None) -> bool:
    if summary is None:
        return False
    if isinstance(summary, SolverLogSummary):
        return summary.completed
    return bool(summary.get("completed"))


def _solver_log_warnings(summary: SolverLogSummary | dict[str, Any] | None) -> list[str]:
    if summary is None:
        return []
    if isinstance(summary, SolverLogSummary):
        return list(summary.warnings)
    warnings = summary.get("warnings") if isinstance(summary, dict) else []
    return [str(item) for item in warnings] if isinstance(warnings, list) else []


def _parameter_source(spec: ThermalSimulationSpec, name: str) -> str:
    for parameter in spec.parameters:
        if parameter.name == name:
            return parameter.source
    return "missing"


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _number_from(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
