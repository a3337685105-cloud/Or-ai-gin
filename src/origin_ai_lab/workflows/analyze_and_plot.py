from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from origin_ai_lab.agents.planner import choose_xy_columns, plan_task
from origin_ai_lab.agents.data_router import route_dataset_auto
from origin_ai_lab.connectors.csv_table import profile_csv, write_normalized_csv
from origin_ai_lab.connectors.origin_client import OriginClient, OriginUnavailable
from origin_ai_lab.connectors.python_analysis import linear_regression_from_csv
from origin_ai_lab.evaluation.checks import (
    check_columns_exist,
    check_columns_numeric,
    check_dataset_has_rows,
    check_regression_sane,
)
from origin_ai_lab.evaluation.plot_accuracy import (
    detect_peak_candidates,
    evaluate_plot_accuracy,
    fit_line_from_regression,
)
from origin_ai_lab.evaluation.visual_quality import evaluate_image_quality
from origin_ai_lab.models import AnalysisTask, PlotKind, PlotSpec, RouteDecision, TaskType, WorkflowResult
from origin_ai_lab.origin_analysis_adapters import planned_origin_adapters
from origin_ai_lab.origin_templates import OriginTaskTemplate, select_origin_template
from origin_ai_lab.plotting.style_defaults import default_axis_title, default_plot_style, default_plot_title


def run_analysis(task: AnalysisTask, output_dir: Path, plot_spec: PlotSpec | None = None) -> WorkflowResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    profile = profile_csv(task.dataset_path)
    normalized_csv_path = write_normalized_csv(task.dataset_path, output_dir / "normalized_data.csv")
    route_decision = route_dataset_auto(task.goal, profile)
    origin_template = select_origin_template(route_decision, profile, task.plot_kind)
    effective_task = _task_with_route_hints(task, route_decision)
    if plot_spec is None:
        x_column, y_column = choose_xy_columns(profile, effective_task.x_column, effective_task.y_column)
        plot_spec = build_plot_spec(effective_task, x_column, y_column, origin_template, route_decision)
    else:
        x_column, y_column = choose_xy_columns(profile, plot_spec.x_column, plot_spec.y_column)

    checks = [
        check_dataset_has_rows(profile),
        check_columns_exist(profile, x_column, y_column),
        check_columns_numeric(profile, x_column, y_column),
    ]

    regression = None
    if (
        plot_spec.fit_enabled
        and all(check.passed for check in checks)
        and task.task_type in {TaskType.REGRESSION, TaskType.PLOT_XY}
    ):
        regression = linear_regression_from_csv(task.dataset_path, x_column, y_column)
        checks.extend(check_regression_sane(regression))

    data_checks_passed = all(check.passed for check in checks if check.name in {"dataset_has_rows", "columns_exist", "columns_numeric"})
    peak_candidates: tuple[dict[str, float], ...] = ()
    fit_line = None
    if data_checks_passed:
        if _route_expects_peaks(route_decision, plot_spec):
            peak_candidates = detect_peak_candidates(task.dataset_path, x_column, y_column)
        if plot_spec.fit_enabled and regression is not None:
            fit_line = fit_line_from_regression(task.dataset_path, x_column, y_column, regression)

    artifacts: dict[str, str] = {}
    artifacts["normalized_csv"] = str(normalized_csv_path)
    route_path = output_dir / "route_decision.json"
    route_path.write_text(json.dumps(route_decision.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts["route_decision"] = str(route_path)

    template_path = output_dir / "origin_template.json"
    template_path.write_text(json.dumps(origin_template.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts["origin_template"] = str(template_path)

    plan = plan_task(profile, effective_task)
    plan_path = output_dir / "plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts["plan"] = str(plan_path)

    plot_spec_path = output_dir / "plot_spec.json"
    plot_spec_path.write_text(json.dumps(plot_spec.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts["plot_spec"] = str(plot_spec_path)

    adapters = planned_origin_adapters(plot_spec, route_decision, peak_candidates)
    adapters_path = output_dir / "origin_analysis_adapters.json"
    adapters_path.write_text(
        json.dumps([adapter.to_dict() for adapter in adapters], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    artifacts["origin_analysis_adapters"] = str(adapters_path)

    if peak_candidates:
        peak_summary_path = output_dir / "peak_summary.json"
        peak_summary_path.write_text(
            json.dumps(
                {
                    "schema_version": "peak-summary/v1",
                    "x_column": x_column,
                    "y_column": y_column,
                    "instrument_family": route_decision.instrument_family,
                    "peaks": list(peak_candidates),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        artifacts["peak_summary"] = str(peak_summary_path)

    origin_render_metadata: dict[str, object] | None = None
    if task.use_origin:
        try:
            with OriginClient(visible=True) as origin:
                origin_artifacts = origin.create_scatter_project(
                    csv_path=task.dataset_path,
                    import_csv_path=normalized_csv_path,
                    output_dir=output_dir,
                    x_column=x_column,
                    y_column=y_column,
                    plot_kind=plot_spec.plot_kind.value,
                    title=plot_spec.title,
                    x_title=plot_spec.x_title,
                    y_title=plot_spec.y_title,
                    x_limits=plot_spec.x_limits,
                    y_limits=plot_spec.y_limits,
                    fit_line=fit_line,
                    style=plot_spec.style,
                    peak_markers=peak_candidates,
                    output_formats=plot_spec.output_formats,
                )
            artifacts["origin_project"] = str(origin_artifacts.project_path)
            artifacts["origin_figure"] = str(origin_artifacts.figure_path)
            for fmt, figure_path in origin_artifacts.figure_paths.items():
                artifacts[f"origin_figure_{fmt}"] = str(figure_path)
            origin_render_metadata = origin_artifacts.render_metadata
            render_metadata_path = output_dir / "origin_render_metadata.json"
            render_metadata_path.write_text(
                json.dumps(origin_render_metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            artifacts["origin_render_metadata"] = str(render_metadata_path)
            visual_checks, visual_report = evaluate_image_quality(origin_artifacts.figure_path)
            checks.extend(visual_checks)
            visual_path = output_dir / "visual_quality.json"
            visual_path.write_text(json.dumps(visual_report, ensure_ascii=False, indent=2), encoding="utf-8")
            artifacts["visual_quality"] = str(visual_path)
        except OriginUnavailable as exc:
            checks.append(
                type(checks[0])(
                    name="origin_available",
                    passed=False,
                    message=str(exc),
                    severity="warning",
                )
            )

    plot_accuracy_checks, plot_accuracy_report = evaluate_plot_accuracy(
        plot_spec=plot_spec,
        profile=profile,
        regression=regression,
        route_decision=route_decision,
        peak_candidates=peak_candidates,
        render_metadata=origin_render_metadata,
    )
    checks.extend(plot_accuracy_checks)
    plot_accuracy_path = output_dir / "plot_accuracy.json"
    plot_accuracy_path.write_text(json.dumps(plot_accuracy_report, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts["plot_accuracy"] = str(plot_accuracy_path)

    result = WorkflowResult(profile=profile, regression=regression, plot_spec=plot_spec, checks=checks, artifacts=artifacts)
    result_path = output_dir / "result.json"
    artifacts["result"] = str(result_path)
    result_path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def build_plot_spec(
    task: AnalysisTask,
    x_column: str,
    y_column: str,
    origin_template: OriginTaskTemplate | None = None,
    route_decision: RouteDecision | None = None,
) -> PlotSpec:
    plot_kind = task.plot_kind if task.plot_kind != PlotKind.AUTO else PlotKind.SCATTER
    if task.plot_kind == PlotKind.AUTO and origin_template is not None:
        plot_kind = origin_template.plot_kind
    fit_enabled = _resolve_fit_enabled(task, origin_template)
    style = default_plot_style(
        plot_kind=plot_kind,
        origin_template=origin_template,
        route_decision=route_decision,
        user_style=task.style,
        group_column=task.group_column,
        fit_enabled=fit_enabled,
    )
    title = task.style.get("title") if isinstance(task.style.get("title"), str) else default_plot_title(x_column, y_column, origin_template)
    x_title = task.style.get("x_title") if isinstance(task.style.get("x_title"), str) else default_axis_title(x_column)
    y_title = task.style.get("y_title") if isinstance(task.style.get("y_title"), str) else default_axis_title(y_column)
    return PlotSpec(
        dataset_path=task.dataset_path,
        plot_kind=plot_kind,
        x_column=x_column,
        y_column=y_column,
        group_column=task.group_column,
        title=title,
        x_title=x_title,
        y_title=y_title,
        fit_enabled=fit_enabled,
        style=style,
        output_formats=task.output_formats or ("png",),
        source_request=task.goal,
    )


def _task_with_route_hints(task: AnalysisTask, route_decision: RouteDecision) -> AnalysisTask:
    x_column = task.x_column or route_decision.x_column
    y_column = task.y_column or route_decision.y_column
    group_column = task.group_column or route_decision.group_column
    plot_kind = task.plot_kind
    route_plot_kind = route_decision.plot_kind
    if route_plot_kind != PlotKind.AUTO and (task.plot_kind == PlotKind.AUTO or not _explicit_plot_kind_requested(task.goal)):
        plot_kind = route_plot_kind
    return replace(
        task,
        x_column=x_column,
        y_column=y_column,
        group_column=group_column,
        plot_kind=plot_kind,
    )


def _explicit_plot_kind_requested(text: str) -> bool:
    normalized = text.lower()
    return any(
        keyword in text or keyword in normalized
        for keyword in ("散点", "折线", "曲线", "柱状", "柱形", "直方", "scatter", "line", "bar", "hist")
    )


def _resolve_fit_enabled(task: AnalysisTask, origin_template: OriginTaskTemplate | None = None) -> bool:
    if task.fit_enabled is not None:
        return task.fit_enabled
    text = task.goal.lower()
    negative = ("不要拟合", "不需要拟合", "去掉拟合", "删除拟合", "不用拟合", "no fit", "without fit")
    if any(item in text for item in negative):
        return False
    positive = ("线性拟合", "加拟合", "拟合线", "linear fit", "regression")
    if any(item in text for item in positive):
        return True
    if origin_template is not None:
        return origin_template.default_fit_enabled
    return True


def _route_expects_peaks(route_decision: RouteDecision, plot_spec: PlotSpec) -> bool:
    return route_decision.instrument_family in {"xrd", "raman"} and plot_spec.plot_kind == PlotKind.LINE
