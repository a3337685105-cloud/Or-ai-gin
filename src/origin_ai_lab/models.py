from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TaskType(str, Enum):
    DESCRIBE = "describe"
    REGRESSION = "regression"
    PLOT_XY = "plot_xy"


class IntentKind(str, Enum):
    CREATE_PLOT = "create_plot"
    MODIFY_PLOT = "modify_plot"
    ANALYZE = "analyze"
    EXPORT = "export"
    UNKNOWN = "unknown"


class PlotKind(str, Enum):
    AUTO = "auto"
    SCATTER = "scatter"
    LINE = "line"
    BAR = "bar"
    HISTOGRAM = "histogram"


class SimulationBackend(str, Enum):
    DRY_RUN = "dry-run"
    MOCK = "mock"
    COMSOL = "comsol"


@dataclass(frozen=True)
class ClarifyingQuestion:
    field: str
    question: str
    options: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "question": self.question,
            "options": list(self.options),
        }


@dataclass(frozen=True)
class RequirementIntent:
    raw_text: str
    kind: IntentKind
    confidence: float
    task_type: TaskType
    plot_kind: PlotKind = PlotKind.AUTO
    x_column: str | None = None
    y_column: str | None = None
    group_column: str | None = None
    style: dict[str, str] = field(default_factory=dict)
    output_formats: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    clarifying_questions: tuple[ClarifyingQuestion, ...] = ()

    @property
    def ready_to_execute(self) -> bool:
        return not self.clarifying_questions and self.kind != IntentKind.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "kind": self.kind.value,
            "confidence": self.confidence,
            "task_type": self.task_type.value,
            "plot_kind": self.plot_kind.value,
            "x_column": self.x_column,
            "y_column": self.y_column,
            "group_column": self.group_column,
            "style": self.style,
            "output_formats": list(self.output_formats),
            "assumptions": list(self.assumptions),
            "clarifying_questions": [question.to_dict() for question in self.clarifying_questions],
            "ready_to_execute": self.ready_to_execute,
        }


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    non_empty: int
    numeric: int
    examples: tuple[str, ...] = ()

    @property
    def numeric_ratio(self) -> float:
        if self.non_empty == 0:
            return 0.0
        return self.numeric / self.non_empty

    @property
    def is_numeric(self) -> bool:
        return self.non_empty > 0 and self.numeric_ratio >= 0.9


@dataclass(frozen=True)
class DatasetProfile:
    path: Path
    row_count: int
    columns: tuple[ColumnProfile, ...]

    def numeric_columns(self) -> list[str]:
        return [column.name for column in self.columns if column.is_numeric]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "row_count": self.row_count,
            "columns": [
                {
                    "name": column.name,
                    "non_empty": column.non_empty,
                    "numeric": column.numeric,
                    "numeric_ratio": column.numeric_ratio,
                    "examples": list(column.examples),
                }
                for column in self.columns
            ],
        }


@dataclass(frozen=True)
class RouteDecision:
    route: str
    planner: str
    confidence: float
    instrument_family: str | None = None
    plot_kind: PlotKind = PlotKind.AUTO
    x_column: str | None = None
    y_column: str | None = None
    group_column: str | None = None
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    clarifying_questions: tuple[ClarifyingQuestion, ...] = ()
    schema_version: str = "route-decision/v1"

    @property
    def ready_to_execute(self) -> bool:
        return self.route not in {"clarify", "unsupported"} and not self.clarifying_questions

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "route": self.route,
            "planner": self.planner,
            "confidence": self.confidence,
            "instrument_family": self.instrument_family,
            "plot_kind": self.plot_kind.value,
            "x_column": self.x_column,
            "y_column": self.y_column,
            "group_column": self.group_column,
            "assumptions": list(self.assumptions),
            "warnings": list(self.warnings),
            "clarifying_questions": [question.to_dict() for question in self.clarifying_questions],
            "ready_to_execute": self.ready_to_execute,
        }


@dataclass(frozen=True)
class AnalysisTask:
    dataset_path: Path
    goal: str
    task_type: TaskType = TaskType.PLOT_XY
    x_column: str | None = None
    y_column: str | None = None
    group_column: str | None = None
    plot_kind: PlotKind = PlotKind.SCATTER
    style: dict[str, Any] = field(default_factory=dict)
    output_formats: tuple[str, ...] = ("png",)
    fit_enabled: bool | None = None
    use_origin: bool = False


@dataclass(frozen=True)
class SimulationParameter:
    name: str
    value: float
    unit: str | None = None
    source: str = "user"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
        }


@dataclass(frozen=True)
class ThermalSimulationTask:
    goal: str
    template_id: str = "generic_stationary_heat"
    template_path: Path | None = None
    backend: SimulationBackend = SimulationBackend.MOCK
    parameters: dict[str, float] = field(default_factory=dict)
    outputs: tuple[str, ...] = ("max_temperature_C", "thermal_summary_csv")
    study_type: str = "stationary"


@dataclass(frozen=True)
class ThermalSimulationSpec:
    source_request: str
    template_id: str
    parameters: tuple[SimulationParameter, ...]
    backend: SimulationBackend = SimulationBackend.MOCK
    template_path: Path | None = None
    study_type: str = "stationary"
    outputs: tuple[str, ...] = ("max_temperature_C", "thermal_summary_csv")
    assumptions: tuple[str, ...] = ()
    schema_version: str = "thermal-simulation-spec/v1"

    def parameter_map(self) -> dict[str, float]:
        return {parameter.name: parameter.value for parameter in self.parameters}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_request": self.source_request,
            "template_id": self.template_id,
            "template_path": str(self.template_path) if self.template_path else None,
            "backend": self.backend.value,
            "study_type": self.study_type,
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "outputs": list(self.outputs),
            "assumptions": list(self.assumptions),
        }


@dataclass(frozen=True)
class VisualizationViewSpec:
    view_id: str
    title: str
    role: str
    output_kind: str
    renderer: str
    view_type: str
    quantity: str
    unit: str | None = None
    artifact_format: str = "png"
    artifact_path: str | None = None
    status: str = "planned"
    placeholder: bool = True
    colorbar_required: bool = True
    color_scale_policy: str = "global_temperature"
    state_label: str = "stationary/base_case"
    required_annotations: tuple[str, ...] = ()
    linked_metrics: tuple[str, ...] = ()
    linked_data: tuple[str, ...] = ()
    expected_frames: int | None = None
    frame_rate_fps: float | None = None
    frame_labels: tuple[str, ...] = ()
    frames: tuple[dict[str, Any], ...] = ()
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "view_id": self.view_id,
            "title": self.title,
            "role": self.role,
            "output_kind": self.output_kind,
            "renderer": self.renderer,
            "view_type": self.view_type,
            "quantity": self.quantity,
            "unit": self.unit,
            "artifact_format": self.artifact_format,
            "artifact_path": self.artifact_path,
            "status": self.status,
            "placeholder": self.placeholder,
            "colorbar_required": self.colorbar_required,
            "color_scale_policy": self.color_scale_policy,
            "state_label": self.state_label,
            "required_annotations": list(self.required_annotations),
            "linked_metrics": list(self.linked_metrics),
            "linked_data": list(self.linked_data),
            "expected_frames": self.expected_frames,
            "frame_rate_fps": self.frame_rate_fps,
            "frame_labels": list(self.frame_labels),
            "frames": [dict(frame) for frame in self.frames],
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class VisualizationSpec:
    source_request: str
    case_id: str
    study_type: str
    views: tuple[VisualizationViewSpec, ...]
    render_policy: dict[str, Any] = field(default_factory=dict)
    global_color_scale: dict[str, Any] = field(default_factory=dict)
    source_work_order: dict[str, Any] = field(default_factory=dict)
    schema_version: str = "thermal-visualization-spec/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "source_request": self.source_request,
            "case_id": self.case_id,
            "study_type": self.study_type,
            "render_policy": self.render_policy,
            "global_color_scale": self.global_color_scale,
            "source_work_order": self.source_work_order,
            "views": [view.to_dict() for view in self.views],
        }


@dataclass(frozen=True)
class PlotSpec:
    dataset_path: Path
    plot_kind: PlotKind
    x_column: str | None
    y_column: str | None
    group_column: str | None = None
    title: str | None = None
    x_title: str | None = None
    y_title: str | None = None
    x_limits: tuple[float | None, float | None] | None = None
    y_limits: tuple[float | None, float | None] | None = None
    fit_enabled: bool = True
    fit_model: str = "linear"
    style: dict[str, Any] = field(default_factory=dict)
    output_formats: tuple[str, ...] = ("png",)
    source_request: str = ""
    schema_version: str = "plot-spec/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "dataset_path": str(self.dataset_path),
            "plot_kind": self.plot_kind.value,
            "x_column": self.x_column,
            "y_column": self.y_column,
            "group_column": self.group_column,
            "title": self.title,
            "x_title": self.x_title,
            "y_title": self.y_title,
            "x_limits": list(self.x_limits) if self.x_limits else None,
            "y_limits": list(self.y_limits) if self.y_limits else None,
            "fit_enabled": self.fit_enabled,
            "fit_model": self.fit_model,
            "style": self.style,
            "output_formats": list(self.output_formats),
            "source_request": self.source_request,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlotSpec":
        return cls(
            schema_version=str(data.get("schema_version") or "plot-spec/v1"),
            dataset_path=Path(str(data["dataset_path"])),
            plot_kind=PlotKind(str(data.get("plot_kind") or data.get("kind") or PlotKind.SCATTER.value)),
            x_column=_optional_str(data.get("x_column")),
            y_column=_optional_str(data.get("y_column")),
            group_column=_optional_str(data.get("group_column")),
            title=_optional_str(data.get("title")),
            x_title=_optional_str(data.get("x_title")),
            y_title=_optional_str(data.get("y_title")),
            x_limits=_limits_from_json(data.get("x_limits")),
            y_limits=_limits_from_json(data.get("y_limits")),
            fit_enabled=bool(data.get("fit_enabled", True)),
            fit_model=str(data.get("fit_model") or "linear"),
            style=data.get("style") if isinstance(data.get("style"), dict) else {},
            output_formats=tuple(str(item).lower() for item in data.get("output_formats", ["png"])),
            source_request=str(data.get("source_request") or ""),
        )


@dataclass(frozen=True)
class PlotEditOperation:
    op: str
    target: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "target": self.target,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlotEditOperation":
        return cls(
            op=str(data.get("op") or ""),
            target=_optional_str(data.get("target")),
            properties=data.get("properties") if isinstance(data.get("properties"), dict) else {},
        )


@dataclass(frozen=True)
class PlotEditPlan:
    user_request: str
    operations: tuple[PlotEditOperation, ...]
    assumptions: tuple[str, ...] = ()
    clarifying_questions: tuple[ClarifyingQuestion, ...] = ()
    requires_confirmation: bool = False
    schema_version: str = "plot-edit-plan/v1"

    @property
    def ready_to_execute(self) -> bool:
        return bool(self.operations) and not self.clarifying_questions and not self.requires_confirmation

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "user_request": self.user_request,
            "operations": [operation.to_dict() for operation in self.operations],
            "assumptions": list(self.assumptions),
            "clarifying_questions": [question.to_dict() for question in self.clarifying_questions],
            "requires_confirmation": self.requires_confirmation,
            "ready_to_execute": self.ready_to_execute,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlotEditPlan":
        return cls(
            schema_version=str(data.get("schema_version") or "plot-edit-plan/v1"),
            user_request=str(data.get("user_request") or ""),
            operations=tuple(
                PlotEditOperation.from_dict(item)
                for item in data.get("operations", [])
                if isinstance(item, dict)
            ),
            assumptions=tuple(str(item) for item in data.get("assumptions", []) if item is not None),
            clarifying_questions=tuple(
                ClarifyingQuestion(
                    field=str(item.get("field", "unknown")),
                    question=str(item.get("question", "")),
                    options=tuple(str(option) for option in item.get("options", []) if option is not None),
                )
                for item in data.get("clarifying_questions", [])
                if isinstance(item, dict)
            ),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
        )


@dataclass(frozen=True)
class PlotRevision:
    run_id: str
    revision: int
    request: str
    output_dir: Path
    plot_spec_path: Path
    result_path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "revision": self.revision,
            "request": self.request,
            "output_dir": str(self.output_dir),
            "plot_spec_path": str(self.plot_spec_path),
            "result_path": str(self.result_path) if self.result_path else None,
        }


@dataclass(frozen=True)
class RegressionResult:
    x_column: str
    y_column: str
    slope: float
    intercept: float
    r_squared: float
    n: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "x_column": self.x_column,
            "y_column": self.y_column,
            "slope": self.slope,
            "intercept": self.intercept,
            "r_squared": self.r_squared,
            "n": self.n,
        }


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class WorkflowResult:
    profile: DatasetProfile
    regression: RegressionResult | None
    plot_spec: PlotSpec | None = None
    checks: list[CheckResult] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks if check.severity == "error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict(),
            "regression": self.regression.to_dict() if self.regression else None,
            "plot_spec": self.plot_spec.to_dict() if self.plot_spec else None,
            "checks": [check.to_dict() for check in self.checks],
            "artifacts": self.artifacts,
            "passed": self.passed,
        }


@dataclass
class ThermalSimulationResult:
    spec: ThermalSimulationSpec
    checks: list[CheckResult] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    status: str = "planned"

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks if check.severity == "error")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "thermal-simulation-result/v1",
            "status": self.status,
            "spec": self.spec.to_dict(),
            "metrics": self.metrics,
            "checks": [check.to_dict() for check in self.checks],
            "artifacts": self.artifacts,
            "passed": self.passed,
        }


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _limits_from_json(value: Any) -> tuple[float | None, float | None] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    begin = None if value[0] is None else float(value[0])
    end = None if value[1] is None else float(value[1])
    return (begin, end)
