from __future__ import annotations

from math import isfinite
from pathlib import Path
from typing import Any

from origin_ai_lab.connectors.csv_table import numeric_pairs
from origin_ai_lab.models import CheckResult, DatasetProfile, PlotKind, PlotSpec, RegressionResult, RouteDecision


PEAK_FAMILIES = {"xrd", "raman"}
MAX_PEAK_MARKERS = 5


def detect_peak_candidates(
    path: Path,
    x_column: str,
    y_column: str,
    max_peaks: int = MAX_PEAK_MARKERS,
) -> tuple[dict[str, float], ...]:
    pairs = numeric_pairs(path, x_column, y_column)
    if len(pairs) < 3:
        return ()

    ys = [point[1] for point in pairs]
    y_min = min(ys)
    y_max = max(ys)
    span = y_max - y_min
    if span <= 0:
        return ()

    min_height = y_min + span * 0.25
    min_prominence = span * 0.05
    candidates: list[dict[str, float]] = []
    for index in range(1, len(pairs) - 1):
        x_value, y_value = pairs[index]
        left_y = pairs[index - 1][1]
        right_y = pairs[index + 1][1]
        surrounding = max(left_y, right_y)
        prominence = y_value - surrounding
        if y_value < min_height or prominence < min_prominence:
            continue
        if y_value > left_y and y_value >= right_y:
            candidates.append(
                {
                    "x": float(x_value),
                    "y": float(y_value),
                    "baseline_y": float(max(y_min, min(left_y, right_y))),
                    "prominence": float(prominence),
                }
            )

    candidates.sort(key=lambda item: (item["prominence"], item["y"]), reverse=True)
    return tuple(candidates[:max(0, max_peaks)])


def fit_line_from_regression(
    path: Path,
    x_column: str,
    y_column: str,
    regression: RegressionResult | None,
) -> dict[str, float] | None:
    if regression is None:
        return None
    pairs = numeric_pairs(path, x_column, y_column)
    if not pairs:
        return None
    xs = [point[0] for point in pairs]
    x1 = min(xs)
    x2 = max(xs)
    y1 = regression.slope * x1 + regression.intercept
    y2 = regression.slope * x2 + regression.intercept
    if not all(isfinite(value) for value in (x1, y1, x2, y2)):
        return None
    return {
        "x1": float(x1),
        "y1": float(y1),
        "x2": float(x2),
        "y2": float(y2),
        "slope": float(regression.slope),
        "intercept": float(regression.intercept),
        "r_squared": float(regression.r_squared),
    }


def evaluate_plot_accuracy(
    plot_spec: PlotSpec,
    profile: DatasetProfile,
    regression: RegressionResult | None = None,
    route_decision: RouteDecision | None = None,
    peak_candidates: tuple[dict[str, float], ...] = (),
    render_metadata: dict[str, Any] | None = None,
) -> tuple[list[CheckResult], dict[str, Any]]:
    expected_x_title = plot_spec.x_title or plot_spec.x_column or ""
    expected_y_title = plot_spec.y_title or plot_spec.y_column or ""
    expected = {
        "title": plot_spec.title,
        "x_axis_title": expected_x_title,
        "y_axis_title": expected_y_title,
        "x_column": plot_spec.x_column,
        "y_column": plot_spec.y_column,
        "plot_kind": plot_spec.plot_kind.value,
        "fit_enabled": plot_spec.fit_enabled,
        "instrument_family": route_decision.instrument_family if route_decision else None,
    }
    checks: list[CheckResult] = []

    checks.append(_axis_title_check(expected_x_title, expected_y_title))
    checks.append(_label_text_safety_check(plot_spec))
    checks.append(_fit_expectation_check(plot_spec, regression))

    if _expects_peak_markers(plot_spec, route_decision):
        checks.append(
            CheckResult(
                "plot_peak_candidates_detected",
                bool(peak_candidates),
                f"{len(peak_candidates)} peak candidate(s) detected for the routed spectrum.",
            )
        )

    if render_metadata:
        checks.extend(
            _render_metadata_checks(
                plot_spec=plot_spec,
                expected_x_title=expected_x_title,
                expected_y_title=expected_y_title,
                route_decision=route_decision,
                peak_candidates=peak_candidates,
                render_metadata=render_metadata,
            )
        )

    report: dict[str, Any] = {
        "schema_version": "plot-accuracy/v1",
        "dataset_path": str(plot_spec.dataset_path),
        "profile": {
            "row_count": profile.row_count,
            "columns": [column.name for column in profile.columns],
        },
        "expected": expected,
        "peak_candidates": list(peak_candidates),
        "render_metadata": render_metadata or {},
        "checks": [check.to_dict() for check in checks],
    }
    report["passed"] = all(check.passed for check in checks if check.severity == "error")
    return checks, report


def _axis_title_check(expected_x_title: str, expected_y_title: str) -> CheckResult:
    passed = bool(expected_x_title and expected_y_title)
    message = (
        f"Expected axis titles are x={expected_x_title!r}, y={expected_y_title!r}."
        if passed
        else "Plot spec must declare both x and y axis titles."
    )
    return CheckResult("plot_axis_titles_declared", passed, message)


def _label_text_safety_check(plot_spec: PlotSpec) -> CheckResult:
    labels = {
        "title": plot_spec.title,
        "x_title": plot_spec.x_title,
        "y_title": plot_spec.y_title,
        "x_column": plot_spec.x_column,
        "y_column": plot_spec.y_column,
    }
    unsafe = {
        name: value
        for name, value in labels.items()
        if isinstance(value, str) and not _safe_label_text(value)
    }
    if not unsafe:
        return CheckResult("plot_label_text_safe", True, "Plot labels contain no hard encoding replacement markers.")
    return CheckResult(
        "plot_label_text_safe",
        False,
        "Unsafe label text detected: " + ", ".join(f"{name}={value!r}" for name, value in unsafe.items()),
    )


def _fit_expectation_check(plot_spec: PlotSpec, regression: RegressionResult | None) -> CheckResult:
    if plot_spec.fit_enabled:
        return CheckResult(
            "plot_fit_expectation",
            regression is not None,
            "Linear fit is enabled and regression data is available."
            if regression is not None
            else "Linear fit is enabled but no regression result was produced.",
        )
    return CheckResult(
        "plot_fit_expectation",
        True,
        "Linear fit is disabled for this plot spec.",
    )


def _render_metadata_checks(
    plot_spec: PlotSpec,
    expected_x_title: str,
    expected_y_title: str,
    route_decision: RouteDecision | None,
    peak_candidates: tuple[dict[str, float], ...],
    render_metadata: dict[str, Any],
) -> list[CheckResult]:
    rendered_x_title = str(render_metadata.get("x_axis_title") or "")
    rendered_y_title = str(render_metadata.get("y_axis_title") or "")
    fit_line_rendered = bool(render_metadata.get("fit_line_rendered"))
    rendered_peak_count = int(render_metadata.get("peak_markers_rendered") or 0)
    checks = [
        CheckResult(
            "origin_axis_titles_match",
            _same_text(rendered_x_title, expected_x_title) and _same_text(rendered_y_title, expected_y_title),
            (
                "Origin-rendered axis titles match the plot spec: "
                f"x={rendered_x_title!r}, y={rendered_y_title!r}."
            ),
        ),
        CheckResult(
            "origin_fit_line_rendered",
            fit_line_rendered if plot_spec.fit_enabled else not fit_line_rendered,
            "Origin fit-line render state matches the plot spec.",
        ),
        _origin_export_formats_check(plot_spec, render_metadata),
    ]

    if _expects_peak_markers(plot_spec, route_decision):
        expected_count = min(len(peak_candidates), MAX_PEAK_MARKERS)
        checks.append(
            CheckResult(
                "origin_peak_markers_rendered",
                rendered_peak_count >= expected_count and expected_count > 0,
                f"Origin rendered {rendered_peak_count}/{expected_count} expected peak marker(s).",
            )
        )

    if plot_spec.group_column or plot_spec.fit_enabled:
        legend_text = str(render_metadata.get("legend_text") or "")
        checks.append(
            CheckResult(
                "origin_legend_present",
                bool(legend_text.strip()),
                "Origin legend text is present." if legend_text.strip() else "Origin legend text was not detected.",
                severity="warning",
            )
        )
    return checks


def _origin_export_formats_check(plot_spec: PlotSpec, render_metadata: dict[str, Any]) -> CheckResult:
    requested = {str(item).lower() for item in plot_spec.output_formats if str(item).lower() != "opju"}
    exported = {str(item).lower() for item in render_metadata.get("exported_formats", [])}
    missing = sorted(requested - exported)
    if not missing:
        return CheckResult(
            "origin_export_formats",
            True,
            "Origin exported all requested figure format(s).",
        )
    return CheckResult(
        "origin_export_formats",
        False,
        "Origin did not export requested figure format(s): " + ", ".join(missing),
    )


def _expects_peak_markers(plot_spec: PlotSpec, route_decision: RouteDecision | None) -> bool:
    family = route_decision.instrument_family if route_decision else None
    return family in PEAK_FAMILIES and plot_spec.plot_kind == PlotKind.LINE


def _same_text(left: str, right: str) -> bool:
    return left.strip() == right.strip()


def _safe_label_text(value: str) -> bool:
    return "\ufffd" not in value and "\x00" not in value
