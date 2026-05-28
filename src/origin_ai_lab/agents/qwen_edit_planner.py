from __future__ import annotations

import json
import os
import re
from typing import Any

from origin_ai_lab.agents.qwen_planner import (
    QwenConfig,
    QwenPlannerError,
    _parse_json_content,
    _post_chat_completion,
)
from origin_ai_lab.models import (
    ClarifyingQuestion,
    DatasetProfile,
    PlotEditOperation,
    PlotEditPlan,
    PlotSpec,
)


COLOR_WORDS = {
    "红": "red",
    "红色": "red",
    "red": "red",
    "蓝": "blue",
    "蓝色": "blue",
    "blue": "blue",
    "绿": "green",
    "绿色": "green",
    "green": "green",
    "黑": "black",
    "黑色": "black",
    "black": "black",
    "灰": "gray",
    "灰色": "gray",
    "gray": "gray",
    "橙": "orange",
    "橙色": "orange",
    "orange": "orange",
    "紫": "purple",
    "紫色": "purple",
    "purple": "purple",
}


def infer_edit_plan_auto(
    request: str,
    current_spec: PlotSpec,
    profile: DatasetProfile | None = None,
) -> PlotEditPlan:
    requested = os.getenv("ORIGIN_AI_EDIT_PLANNER", os.getenv("ORIGIN_AI_PLANNER", "auto")).strip().lower()
    if requested == "rule":
        return infer_edit_plan_rule(request, current_spec, profile)
    config = QwenConfig.from_env()
    if config is not None and requested in {"auto", "qwen"}:
        try:
            return infer_edit_plan_with_qwen(request, current_spec, profile, config)
        except QwenPlannerError:
            if requested == "qwen":
                raise
            pass
    return infer_edit_plan_rule(request, current_spec, profile)


def infer_edit_plan_with_qwen(
    request: str,
    current_spec: PlotSpec,
    profile: DatasetProfile | None = None,
    config: QwenConfig | None = None,
) -> PlotEditPlan:
    active_config = config or QwenConfig.from_env()
    if active_config is None:
        raise QwenPlannerError("DASHSCOPE_API_KEY is not configured.")
    payload = {
        "model": active_config.model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(request, current_spec, profile)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "enable_thinking": active_config.enable_thinking,
    }
    response = _post_chat_completion(active_config, payload)
    content = response["choices"][0]["message"]["content"]
    data = _parse_json_content(content)
    plan = PlotEditPlan.from_dict({**data, "user_request": request})
    return _normalize_model_plan(plan, request, active_config.model)


def _normalize_model_plan(plan: PlotEditPlan, request: str, model: str) -> PlotEditPlan:
    assumptions = list(plan.assumptions)
    if not any(item.startswith("Planner: qwen") for item in assumptions):
        assumptions.insert(0, f"Planner: qwen ({model}).")
    if _is_vague_aesthetic_request(request):
        return PlotEditPlan(
            user_request=plan.user_request,
            operations=(),
            assumptions=tuple(assumptions),
            clarifying_questions=(
                ClarifyingQuestion(
                    field="edit_request",
                    question="这个修改请求偏审美方向，请先选择具体修改方向。",
                    options=("黑白论文风", "更大字号", "矢量导出", "保留当前样式只微调"),
                ),
            ),
            requires_confirmation=True,
            schema_version=plan.schema_version,
        )
    operations = list(plan.operations)
    requested_formats = _find_formats(request.lower())
    if requested_formats:
        operations = [
            PlotEditOperation(operation.op, target=operation.target, properties={"formats": requested_formats})
            if operation.op == "set_export_formats"
            else operation
            for operation in operations
        ]
    if any(item in request for item in ("加粗", "粗一点", "更粗")) or "thick" in request.lower():
        normalized_operations: list[PlotEditOperation] = []
        for operation in operations:
            if operation.op in {"set_fit_style", "set_series_style"}:
                props = dict(operation.properties)
                if "line_width" in props:
                    try:
                        props["line_width"] = max(float(props["line_width"]), 3)
                        if props["line_width"].is_integer():
                            props["line_width"] = int(props["line_width"])
                    except Exception:
                        props["line_width"] = 3
                normalized_operations.append(
                    PlotEditOperation(operation.op, target=operation.target, properties=props)
                )
            else:
                normalized_operations.append(operation)
        operations = normalized_operations
    return PlotEditPlan(
        user_request=plan.user_request,
        operations=tuple(operations),
        assumptions=tuple(assumptions),
        clarifying_questions=plan.clarifying_questions,
        requires_confirmation=plan.requires_confirmation,
        schema_version=plan.schema_version,
    )


def _is_vague_aesthetic_request(request: str) -> bool:
    text = request.lower()
    vague_words = ("论文图", "好看", "美观", "高级", "publication", "paper style")
    specific_words = ("颜色", "红", "蓝", "黑", "标题", "坐标", "拟合", "导出", "svg", "pdf", "png", "线宽", "加粗")
    return any(word in text for word in vague_words) and not any(word in text for word in specific_words)


def infer_edit_plan_rule(
    request: str,
    current_spec: PlotSpec,
    profile: DatasetProfile | None = None,
) -> PlotEditPlan:
    text = request.strip()
    lowered = text.lower()
    operations: list[PlotEditOperation] = []
    assumptions: list[str] = ["Planner: rule edit planner."]

    if any(word in text for word in ("折线", "曲线")) or "line" in lowered:
        operations.append(PlotEditOperation("set_plot_kind", properties={"plot_kind": "line"}))
    if "散点" in text or "scatter" in lowered:
        operations.append(PlotEditOperation("set_plot_kind", properties={"plot_kind": "scatter"}))

    color = _find_color(text, lowered)
    if color:
        operations.append(PlotEditOperation("set_series_style", properties={"color": color}))

    if any(item in text for item in ("加粗", "粗一点", "更粗")) or "thick" in lowered:
        target = "fit_line" if "拟合" in text or "fit" in lowered else "series"
        op = "set_fit_style" if target == "fit_line" else "set_series_style"
        operations.append(PlotEditOperation(op, properties={"line_width": 3}))

    if any(item in text for item in ("不要拟合", "不需要拟合", "去掉拟合", "删除拟合", "不用拟合")) or "no fit" in lowered or "remove fit" in lowered:
        operations.append(PlotEditOperation("set_fit", properties={"enabled": False}))
    elif "拟合" in text or "linear fit" in lowered or "regression" in lowered:
        operations.append(PlotEditOperation("set_fit", properties={"enabled": True, "fit_model": "linear"}))

    formats = _find_formats(lowered)
    if formats:
        operations.append(PlotEditOperation("set_export_formats", properties={"formats": formats}))

    title = _extract_after(text, ("标题改成", "标题改为", "图标题改成", "图标题改为"))
    if title:
        operations.append(PlotEditOperation("set_title", properties={"title": title}))

    x_title = _extract_after(text, ("横坐标标题改成", "横坐标标题改为", "x轴标题改成", "x 轴标题改成"))
    if x_title:
        operations.append(PlotEditOperation("set_axis_title", target="x", properties={"title": x_title}))
    y_title = _extract_after(text, ("纵坐标标题改成", "纵坐标标题改为", "y轴标题改成", "y 轴标题改成"))
    if y_title:
        operations.append(PlotEditOperation("set_axis_title", target="y", properties={"title": y_title}))

    for axis, begin, end in _find_axis_limits(text):
        operations.append(PlotEditOperation("set_axis_limits", target=axis, properties={"begin": begin, "end": end}))

    column_ops = _find_column_changes(text, profile)
    operations.extend(column_ops)

    if not operations:
        return PlotEditPlan(
            user_request=text,
            operations=(),
            assumptions=tuple(assumptions),
            clarifying_questions=(
                ClarifyingQuestion(
                    field="edit_request",
                    question="这个修改请求还不够明确，请说明要改颜色、坐标轴、拟合、标题、导出格式还是数据列。",
                    options=("改颜色", "改坐标轴", "改拟合", "改导出格式"),
                ),
            ),
            requires_confirmation=True,
        )
    return PlotEditPlan(user_request=text, operations=tuple(operations), assumptions=tuple(assumptions))


def _system_prompt() -> str:
    return """
You are the edit planner for Origin AI Lab.
Return only a JSON object. Do not claim that any plot has been modified.

Schema:
{
  "schema_version": "plot-edit-plan/v1",
  "operations": [
    {"op": "set_series_style", "target": null, "properties": {"color": "red"}}
  ],
  "assumptions": ["short assumption"],
  "clarifying_questions": [{"field": "field_name", "question": "question", "options": ["option"]}],
  "requires_confirmation": false
}

Supported operations:
- set_plot_kind: properties.plot_kind = scatter | line
- set_columns: properties.x_column, y_column, group_column
- set_fit: properties.enabled = true | false, optional fit_model = linear
- set_title: properties.title
- set_axis_title: target = x | y, properties.title
- set_axis_limits: target = x | y, properties.begin, properties.end
- set_series_style: properties.color, marker, line_width
- set_fit_style: properties.color, line_width
- set_export_formats: properties.formats = ["png", "svg", "pdf", "opju"]

Rules:
- Use existing column names exactly.
- Ask a blocking clarifying question if the user names a missing column or makes a vague aesthetic request.
- Do not output unsupported operations.
""".strip()


def _user_prompt(request: str, current_spec: PlotSpec, profile: DatasetProfile | None) -> str:
    return json.dumps(
        {
            "user_edit_request": request,
            "current_plot_spec": current_spec.to_dict(),
            "dataset_profile": profile.to_dict() if profile else None,
        },
        ensure_ascii=False,
        indent=2,
    )


def _find_color(text: str, lowered: str) -> str | None:
    for word, color in COLOR_WORDS.items():
        if word in text or word in lowered:
            return color
    return None


def _find_formats(lowered: str) -> list[str]:
    formats = []
    for fmt in ("png", "svg", "pdf", "opju"):
        if fmt in lowered or (fmt == "opju" and "origin" in lowered):
            formats.append(fmt)
    return formats


def _extract_after(text: str, prefixes: tuple[str, ...]) -> str | None:
    for prefix in prefixes:
        if prefix in text:
            value = text.split(prefix, 1)[1].strip(" ：:，,。\"'")
            return value[:80].strip() or None
    return None


def _find_axis_limits(text: str) -> list[tuple[str, float, float]]:
    results: list[tuple[str, float, float]] = []
    axis_patterns = (
        ("x", r"(?:x\s*轴|X\s*轴|横坐标|横轴).*?(?:从|范围)?\s*(-?\d+(?:\.\d+)?)\s*(?:到|至|-|~)\s*(-?\d+(?:\.\d+)?)"),
        ("y", r"(?:y\s*轴|Y\s*轴|纵坐标|纵轴).*?(?:从|范围)?\s*(-?\d+(?:\.\d+)?)\s*(?:到|至|-|~)\s*(-?\d+(?:\.\d+)?)"),
    )
    for axis, pattern in axis_patterns:
        match = re.search(pattern, text)
        if match:
            results.append((axis, float(match.group(1)), float(match.group(2))))
    return results


def _find_column_changes(text: str, profile: DatasetProfile | None) -> list[PlotEditOperation]:
    if profile is None:
        return []
    props: dict[str, str] = {}
    names = [column.name for column in profile.columns]
    for name in names:
        if f"横坐标改成{name}" in text or f"x轴改成{name}" in text or f"x 轴改成{name}" in text:
            props["x_column"] = name
        if f"纵坐标改成{name}" in text or f"y轴改成{name}" in text or f"y 轴改成{name}" in text:
            props["y_column"] = name
        if f"按{name}分组" in text or f"按 {name} 分组" in text or f"按{name}上色" in text:
            props["group_column"] = name
    if props:
        return [PlotEditOperation("set_columns", properties=props)]
    return []
