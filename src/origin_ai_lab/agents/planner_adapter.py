from __future__ import annotations

import os

from origin_ai_lab.agents.qwen_planner import QwenPlannerError, infer_requirement_with_qwen, qwen_status
from origin_ai_lab.agents.requirement_intake import infer_requirement
from origin_ai_lab.models import DatasetProfile, RequirementIntent


def active_planner_name() -> str:
    requested = os.getenv("ORIGIN_AI_PLANNER", "auto").strip().lower()
    status = qwen_status()
    if requested == "qwen":
        return "qwen" if status["configured"] else "qwen_not_configured"
    if requested == "rule":
        return "rule"
    if status["configured"]:
        return "qwen"
    return "rule"


def infer_requirement_auto(raw_text: str, profile: DatasetProfile | None = None) -> RequirementIntent:
    planner = active_planner_name()
    if planner == "qwen":
        try:
            return infer_requirement_with_qwen(raw_text, profile)
        except QwenPlannerError as exc:
            fallback = infer_requirement(raw_text, profile)
            return _with_added_assumption(fallback, f"Qwen planner failed, fell back to rule planner: {exc}")
    return infer_requirement(raw_text, profile)


def _with_added_assumption(intent: RequirementIntent, assumption: str) -> RequirementIntent:
    return RequirementIntent(
        raw_text=intent.raw_text,
        kind=intent.kind,
        confidence=intent.confidence,
        task_type=intent.task_type,
        plot_kind=intent.plot_kind,
        x_column=intent.x_column,
        y_column=intent.y_column,
        group_column=intent.group_column,
        style=intent.style,
        output_formats=intent.output_formats,
        assumptions=(assumption, *intent.assumptions),
        clarifying_questions=intent.clarifying_questions,
    )
