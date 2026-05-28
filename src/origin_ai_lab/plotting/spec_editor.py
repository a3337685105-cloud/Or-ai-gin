from __future__ import annotations

from dataclasses import replace
from typing import Any

from origin_ai_lab.models import DatasetProfile, PlotEditOperation, PlotEditPlan, PlotKind, PlotSpec


class PlotSpecValidationError(ValueError):
    """Raised when an edit plan would create an invalid or unsupported plot spec."""


SUPPORTED_PLOT_KINDS = {PlotKind.SCATTER, PlotKind.LINE}
SUPPORTED_FORMATS = {"png", "svg", "pdf", "opju"}
SUPPORTED_OPERATIONS = {
    "set_plot_kind",
    "set_columns",
    "set_fit",
    "set_title",
    "set_axis_title",
    "set_axis_limits",
    "set_series_style",
    "set_fit_style",
    "set_export_formats",
}


def apply_edit_plan(spec: PlotSpec, plan: PlotEditPlan, profile: DatasetProfile | None = None) -> PlotSpec:
    if not plan.ready_to_execute:
        raise PlotSpecValidationError("Edit plan is not ready to execute.")
    updated = spec
    for operation in plan.operations:
        updated = apply_edit_operation(updated, operation, profile)
    validate_plot_spec(updated, profile)
    return updated


def apply_edit_operation(
    spec: PlotSpec,
    operation: PlotEditOperation,
    profile: DatasetProfile | None = None,
) -> PlotSpec:
    op = _normalize_operation_name(operation.op)
    if op not in SUPPORTED_OPERATIONS:
        raise PlotSpecValidationError(f"Unsupported edit operation: {operation.op}")
    props = operation.properties

    if op == "set_plot_kind":
        plot_kind = _plot_kind_from(props.get("plot_kind") or props.get("kind") or props.get("value"))
        return replace(spec, plot_kind=plot_kind)

    if op == "set_columns":
        x_column = _value_or_current(props, "x_column", spec.x_column)
        y_column = _value_or_current(props, "y_column", spec.y_column)
        group_column = _value_or_current(props, "group_column", spec.group_column)
        _validate_column(x_column, profile, required=True, field="x_column")
        _validate_column(y_column, profile, required=True, field="y_column")
        if group_column:
            _validate_column(group_column, profile, required=False, field="group_column")
        return replace(spec, x_column=x_column, y_column=y_column, group_column=group_column)

    if op == "set_fit":
        enabled = _bool_from(props.get("enabled", props.get("fit_enabled", props.get("value", True))))
        fit_model = str(props.get("fit_model") or props.get("model") or spec.fit_model)
        if fit_model != "linear":
            raise PlotSpecValidationError("Only linear fitting is supported in the MVP.")
        return replace(spec, fit_enabled=enabled, fit_model=fit_model)

    if op == "set_title":
        title = _required_text(props.get("title") or props.get("value"), "title")
        return replace(spec, title=title)

    if op == "set_axis_title":
        axis = _axis_from(operation.target or props.get("axis"))
        title = _required_text(props.get("title") or props.get("value"), "axis title")
        return replace(spec, x_title=title) if axis == "x" else replace(spec, y_title=title)

    if op == "set_axis_limits":
        axis = _axis_from(operation.target or props.get("axis"))
        limits = _limits_from_props(props)
        return replace(spec, x_limits=limits) if axis == "x" else replace(spec, y_limits=limits)

    if op == "set_series_style":
        return replace(spec, style=_merged_style(spec.style, "series", props))

    if op == "set_fit_style":
        return replace(spec, style=_merged_style(spec.style, "fit_line", props))

    if op == "set_export_formats":
        raw_formats = props.get("formats", props.get("value", []))
        if isinstance(raw_formats, str):
            raw_formats = [raw_formats]
        formats = tuple(str(item).lower() for item in raw_formats)
        if not formats:
            raise PlotSpecValidationError("At least one export format is required.")
        unsupported = sorted(set(formats) - SUPPORTED_FORMATS)
        if unsupported:
            raise PlotSpecValidationError(f"Unsupported export format(s): {', '.join(unsupported)}")
        return replace(spec, output_formats=formats)

    raise PlotSpecValidationError(f"Unsupported edit operation: {operation.op}")


def validate_plot_spec(spec: PlotSpec, profile: DatasetProfile | None = None) -> None:
    if spec.plot_kind not in SUPPORTED_PLOT_KINDS:
        raise PlotSpecValidationError(f"Unsupported plot kind for modification MVP: {spec.plot_kind.value}")
    _validate_column(spec.x_column, profile, required=True, field="x_column")
    _validate_column(spec.y_column, profile, required=True, field="y_column")
    if spec.group_column:
        _validate_column(spec.group_column, profile, required=False, field="group_column")
    if spec.fit_model != "linear":
        raise PlotSpecValidationError("Only linear fitting is supported in the MVP.")
    unsupported = sorted(set(spec.output_formats) - SUPPORTED_FORMATS)
    if unsupported:
        raise PlotSpecValidationError(f"Unsupported export format(s): {', '.join(unsupported)}")
    _validate_limits(spec.x_limits, "x_limits")
    _validate_limits(spec.y_limits, "y_limits")


def _normalize_operation_name(name: str) -> str:
    aliases = {
        "set_plot_type": "set_plot_kind",
        "change_plot_kind": "set_plot_kind",
        "change_columns": "set_columns",
        "set_fit_enabled": "set_fit",
        "set_output_formats": "set_export_formats",
        "set_style": "set_series_style",
    }
    return aliases.get(str(name).strip().lower(), str(name).strip().lower())


def _plot_kind_from(value: Any) -> PlotKind:
    try:
        plot_kind = PlotKind(str(value).strip().lower())
    except Exception as exc:
        raise PlotSpecValidationError(f"Unsupported plot kind: {value}") from exc
    if plot_kind not in SUPPORTED_PLOT_KINDS:
        raise PlotSpecValidationError(f"Unsupported plot kind for modification MVP: {plot_kind.value}")
    return plot_kind


def _value_or_current(props: dict[str, Any], key: str, current: str | None) -> str | None:
    if key not in props:
        return current
    value = props[key]
    if value is None or value == "":
        return None
    return str(value)


def _validate_column(
    column: str | None,
    profile: DatasetProfile | None,
    required: bool,
    field: str,
) -> None:
    if not column:
        if required:
            raise PlotSpecValidationError(f"{field} is required.")
        return
    if profile is None:
        return
    existing = {item.name for item in profile.columns}
    if column not in existing:
        raise PlotSpecValidationError(f"Column {column!r} does not exist.")


def _bool_from(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", "none", "null"}


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise PlotSpecValidationError(f"{field} cannot be empty.")
    return text


def _axis_from(value: Any) -> str:
    axis = str(value or "").strip().lower()
    if axis in {"x", "x_axis", "x-axis", "horizontal", "横轴", "横坐标"}:
        return "x"
    if axis in {"y", "y_axis", "y-axis", "vertical", "纵轴", "纵坐标"}:
        return "y"
    raise PlotSpecValidationError(f"Unsupported axis: {value}")


def _limits_from_props(props: dict[str, Any]) -> tuple[float | None, float | None]:
    if "limits" in props and isinstance(props["limits"], (list, tuple)) and len(props["limits"]) == 2:
        begin, end = props["limits"]
    else:
        begin, end = props.get("begin", props.get("min")), props.get("end", props.get("max"))
    begin_value = None if begin is None or begin == "" else float(begin)
    end_value = None if end is None or end == "" else float(end)
    limits = (begin_value, end_value)
    _validate_limits(limits, "axis_limits")
    return limits


def _validate_limits(limits: tuple[float | None, float | None] | None, field: str) -> None:
    if limits is None:
        return
    begin, end = limits
    if begin is not None and end is not None and begin >= end:
        raise PlotSpecValidationError(f"{field} begin must be smaller than end.")


def _merged_style(style: dict[str, Any], key: str, props: dict[str, Any]) -> dict[str, Any]:
    cleaned = {str(name): value for name, value in props.items() if name not in {"target"}}
    merged = dict(style)
    existing = merged.get(key) if isinstance(merged.get(key), dict) else {}
    merged[key] = {**existing, **cleaned}
    return merged
