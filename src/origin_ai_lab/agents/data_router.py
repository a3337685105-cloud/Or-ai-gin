from __future__ import annotations

import json
import os
from dataclasses import replace
from typing import Any

from origin_ai_lab.agents.qwen_planner import (
    QwenConfig,
    QwenPlannerError,
    _parse_json_content,
    _post_chat_completion,
    qwen_status,
)
from origin_ai_lab.models import ClarifyingQuestion, DatasetProfile, PlotKind, RouteDecision


ROUTE_NORMALIZE_TABLE = "normalize_table"
ROUTE_CLARIFY = "clarify"
ROUTE_UNSUPPORTED = "unsupported"
VALID_ROUTES = {ROUTE_NORMALIZE_TABLE, ROUTE_CLARIFY, ROUTE_UNSUPPORTED}


def route_dataset_auto(raw_text: str, profile: DatasetProfile) -> RouteDecision:
    rule = route_dataset_rule(raw_text, profile)
    requested = os.getenv("ORIGIN_AI_ROUTE_PLANNER", "auto").strip().lower()
    if requested == "rule":
        return rule

    configured = qwen_status()["configured"]
    if requested == "qwen":
        if not configured:
            return _with_warning(rule, "Qwen route planner requested but DASHSCOPE_API_KEY is not configured.")
        return _route_with_qwen_or_fallback(raw_text, profile, rule)

    if configured and _needs_ai_route(raw_text, profile, rule):
        return _route_with_qwen_or_fallback(raw_text, profile, rule)
    return rule


def route_dataset_rule(raw_text: str, profile: DatasetProfile) -> RouteDecision:
    numeric_columns = profile.numeric_columns()
    assumptions: list[str] = ["Planner: rule route planner."]
    warnings: list[str] = []
    questions: list[ClarifyingQuestion] = []

    if profile.row_count <= 0:
        return RouteDecision(
            route=ROUTE_UNSUPPORTED,
            planner="rule",
            confidence=0.1,
            assumptions=tuple(assumptions),
            warnings=("No rows were detected in the parsed table.",),
        )

    family = _infer_instrument_family(raw_text, profile)
    plot_kind, x_column, y_column = _infer_plot_slots(raw_text, profile, family)

    confidence = 0.55
    if family:
        confidence += 0.15
    if plot_kind != PlotKind.AUTO:
        confidence += 0.1
    if _slots_ready(plot_kind, x_column, y_column):
        confidence += 0.15
    elif len(numeric_columns) > 2:
        questions.extend(_axis_questions(numeric_columns))

    if not numeric_columns:
        questions.append(
            ClarifyingQuestion(
                field="columns",
                question="没有检测到可用于绘图的数值列，请确认数据表头和数据区。",
            )
        )
        confidence = 0.2

    route = ROUTE_NORMALIZE_TABLE if not questions else ROUTE_CLARIFY
    if not family:
        assumptions.append("No known instrument family was inferred; downstream validators will rely on explicit columns.")
    else:
        assumptions.append(f"Instrument family inferred as {family}.")

    return RouteDecision(
        route=route,
        planner="rule",
        confidence=min(confidence, 0.95),
        instrument_family=family,
        plot_kind=plot_kind,
        x_column=x_column,
        y_column=y_column,
        assumptions=tuple(assumptions),
        warnings=tuple(warnings),
        clarifying_questions=tuple(questions),
    )


def infer_route_with_qwen(
    raw_text: str,
    profile: DatasetProfile,
    rule_decision: RouteDecision,
    config: QwenConfig | None = None,
) -> RouteDecision:
    active_config = config or QwenConfig.from_env()
    if active_config is None:
        raise QwenPlannerError("DASHSCOPE_API_KEY is not configured.")

    payload = {
        "model": active_config.model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(raw_text, profile, rule_decision)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "enable_thinking": active_config.enable_thinking,
    }
    response = _post_chat_completion(active_config, payload)
    content = response["choices"][0]["message"]["content"]
    data = _parse_json_content(content)
    return _route_from_model_json(data, profile, active_config.model, rule_decision)


def _route_with_qwen_or_fallback(raw_text: str, profile: DatasetProfile, rule: RouteDecision) -> RouteDecision:
    try:
        return infer_route_with_qwen(raw_text, profile, rule)
    except QwenPlannerError as exc:
        return _with_warning(rule, f"Qwen route planner failed, fell back to rule planner: {exc}")


def _route_from_model_json(
    data: dict[str, Any],
    profile: DatasetProfile,
    model: str,
    rule_decision: RouteDecision,
) -> RouteDecision:
    route = str(data.get("route") or ROUTE_NORMALIZE_TABLE)
    if route not in VALID_ROUTES:
        route = ROUTE_CLARIFY

    instrument_family = _optional_str(data.get("instrument_family")) or rule_decision.instrument_family
    plot_kind = _plot_kind_or_auto(data.get("plot_kind"))
    x_column = _valid_column_or_none(data.get("x_column"), profile)
    y_column = _valid_column_or_none(data.get("y_column"), profile)
    group_column = _valid_column_or_none(data.get("group_column"), profile, numeric_only=False)
    warnings = [str(item) for item in data.get("warnings", []) if item is not None]
    assumptions = [f"Planner: qwen route planner ({model})."]
    assumptions.extend(str(item) for item in data.get("assumptions", []) if item is not None)

    questions = [
        ClarifyingQuestion(
            field=str(item.get("field", "unknown")),
            question=str(item.get("question", "")),
            options=tuple(str(option) for option in item.get("options", []) if option is not None),
        )
        for item in data.get("clarifying_questions", [])
        if isinstance(item, dict)
    ]
    questions.extend(_invalid_column_questions(data, profile, x_column, y_column, group_column))

    if route != ROUTE_UNSUPPORTED and not _slots_ready(plot_kind, x_column, y_column):
        if not questions:
            questions.extend(_axis_questions(profile.numeric_columns()))
        route = ROUTE_CLARIFY

    return RouteDecision(
        route=route,
        planner="qwen",
        confidence=float(data.get("confidence", 0.8)),
        instrument_family=instrument_family,
        plot_kind=plot_kind,
        x_column=x_column,
        y_column=y_column,
        group_column=group_column,
        assumptions=tuple(assumptions),
        warnings=tuple(warnings),
        clarifying_questions=tuple(questions),
    )


def _infer_instrument_family(raw_text: str, profile: DatasetProfile) -> str | None:
    normalized = raw_text.lower()
    columns = {column.name.lower() for column in profile.columns}
    joined_columns = " ".join(columns)
    if "nyquist" in normalized or "eis" in normalized or "阻抗" in raw_text or {"z_real_ohm", "z_imag_neg_ohm"}.issubset(columns):
        return "eis"
    if "xrd" in normalized or "衍射" in raw_text or "two_theta_deg" in columns or "2theta" in joined_columns:
        return "xrd"
    if "raman" in normalized or "拉曼" in raw_text or "raman_shift_cm-1" in columns:
        return "raman"
    if "tga" in normalized or "热重" in raw_text or {"temperature_c", "mass_percent"}.issubset(columns):
        return "tga"
    if "dsc" in normalized or "热流" in raw_text or "heat_flow_mw" in columns:
        return "dsc"
    if "充放电" in raw_text or "battery" in normalized or {"capacity_mah_g", "voltage_v"}.issubset(columns):
        return "battery"
    if "应力应变" in raw_text or {"strain_percent", "stress_mpa"}.issubset(columns):
        return "stress_strain"
    if "粒径" in raw_text or "particle_diameter_nm" in columns:
        return "particle_size"
    return None


def _infer_plot_slots(
    raw_text: str,
    profile: DatasetProfile,
    family: str | None,
) -> tuple[PlotKind, str | None, str | None]:
    columns = {column.name.lower(): column.name for column in profile.columns}
    if family == "eis":
        return PlotKind.SCATTER, _column(columns, "z_real_ohm"), _column(columns, "z_imag_neg_ohm")
    if family == "xrd":
        return PlotKind.LINE, _first_column(columns, "two_theta_deg", "2theta", "two_theta"), _first_column(columns, "intensity_counts", "intensity")
    if family == "raman":
        return PlotKind.LINE, _first_column(columns, "raman_shift_cm-1", "wavenumber", "shift"), _first_column(columns, "intensity_a.u.", "intensity")
    if family == "tga":
        return PlotKind.LINE, _column(columns, "temperature_c"), _column(columns, "mass_percent")
    if family == "dsc":
        return PlotKind.LINE, _column(columns, "temperature_c"), _column(columns, "heat_flow_mw")
    if family == "battery":
        return PlotKind.LINE, _column(columns, "capacity_mah_g"), _column(columns, "voltage_v")
    if family == "stress_strain":
        return PlotKind.LINE, _column(columns, "strain_percent"), _column(columns, "stress_mpa")
    if family == "particle_size" and ("直方" in raw_text or "hist" in raw_text.lower() or "分布" in raw_text):
        return PlotKind.HISTOGRAM, None, _column(columns, "particle_diameter_nm")

    numeric_columns = profile.numeric_columns()
    if len(numeric_columns) == 2:
        return PlotKind.AUTO, numeric_columns[0], numeric_columns[1]
    return PlotKind.AUTO, None, None


def _needs_ai_route(raw_text: str, profile: DatasetProfile, rule: RouteDecision) -> bool:
    if rule.clarifying_questions:
        return True
    if rule.confidence < 0.6:
        return True
    text = raw_text.lower()
    material_words = ("xrd", "raman", "tga", "dsc", "eis", "nyquist", "拉曼", "衍射", "热重", "阻抗")
    return rule.instrument_family is None and any(word in text or word in raw_text for word in material_words)


def _slots_ready(plot_kind: PlotKind, x_column: str | None, y_column: str | None) -> bool:
    if plot_kind == PlotKind.HISTOGRAM:
        return bool(y_column)
    return bool(x_column and y_column)


def _axis_questions(numeric_columns: list[str]) -> list[ClarifyingQuestion]:
    return [
        ClarifyingQuestion(
            field="x_column",
            question="检测到多个可能的数值列，请确认横轴。",
            options=tuple(numeric_columns),
        ),
        ClarifyingQuestion(
            field="y_column",
            question="检测到多个可能的数值列，请确认纵轴。",
            options=tuple(numeric_columns),
        ),
    ]


def _invalid_column_questions(
    data: dict[str, Any],
    profile: DatasetProfile,
    x_column: str | None,
    y_column: str | None,
    group_column: str | None,
) -> list[ClarifyingQuestion]:
    existing = {column.name for column in profile.columns}
    questions: list[ClarifyingQuestion] = []
    for field, value, resolved in (
        ("x_column", data.get("x_column"), x_column),
        ("y_column", data.get("y_column"), y_column),
        ("group_column", data.get("group_column"), group_column),
    ):
        if value and str(value) not in existing and resolved is None:
            questions.append(
                ClarifyingQuestion(
                    field=field,
                    question=f"AI 路由选择了不存在的列 {value!r}，请确认要使用哪一列。",
                    options=tuple(column.name for column in profile.columns),
                )
            )
    return questions


def _with_warning(decision: RouteDecision, warning: str) -> RouteDecision:
    return replace(decision, warnings=(warning, *decision.warnings))


def _valid_column_or_none(value: Any, profile: DatasetProfile, numeric_only: bool = True) -> str | None:
    if value is None or value == "":
        return None
    column = str(value)
    columns = profile.numeric_columns() if numeric_only else [item.name for item in profile.columns]
    return column if column in set(columns) else None


def _plot_kind_or_auto(value: Any) -> PlotKind:
    try:
        return PlotKind(str(value))
    except Exception:
        return PlotKind.AUTO


def _optional_str(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _column(columns: dict[str, str], name: str) -> str | None:
    return columns.get(name.lower())


def _first_column(columns: dict[str, str], *needles: str) -> str | None:
    for needle in needles:
        exact = columns.get(needle.lower())
        if exact:
            return exact
    for needle in needles:
        for lower_name, original in columns.items():
            if needle.lower() in lower_name:
                return original
    return None


def _system_prompt() -> str:
    return """
You are the routing planner for Origin AI Lab.
Return only a JSON object. You do not execute code and you do not claim that Origin has run.

You receive a user request, a dataset profile, and a deterministic rule decision.
Your job is only to fill a route decision that helps deterministic code choose the import/plot path.

Schema:
{
  "route": "normalize_table | clarify | unsupported",
  "confidence": 0.0,
  "instrument_family": "xrd | raman | tga | dsc | battery | eis | stress_strain | particle_size | null",
  "plot_kind": "auto | scatter | line | bar | histogram",
  "x_column": "existing numeric column or null",
  "y_column": "existing numeric column or null",
  "group_column": "existing column or null",
  "assumptions": ["short assumption"],
  "warnings": ["short warning"],
  "clarifying_questions": [{"field": "x_column", "question": "question", "options": ["column"]}]
}

Rules:
- Use column names exactly as provided in the dataset profile.
- Prefer normalize_table for instrument exports that can be converted into a clean CSV table.
- For XRD/Raman/TGA/DSC/battery/stress-strain spectra or curves, prefer line.
- For EIS/Nyquist, prefer scatter unless the user explicitly asks for connected lines.
- For particle-size distribution histograms, leave x_column null and put the measured value column in y_column.
- If columns are ambiguous, ask a clarifying question instead of guessing.
- Scientific correctness is validated downstream; you only route.
""".strip()


def _user_prompt(raw_text: str, profile: DatasetProfile, rule_decision: RouteDecision) -> str:
    return json.dumps(
        {
            "user_request": raw_text,
            "dataset_profile": profile.to_dict(),
            "rule_decision": rule_decision.to_dict(),
        },
        ensure_ascii=False,
        indent=2,
    )
