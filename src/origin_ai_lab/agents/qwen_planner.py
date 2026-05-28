from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from origin_ai_lab.models import (
    ClarifyingQuestion,
    DatasetProfile,
    IntentKind,
    PlotKind,
    RequirementIntent,
    TaskType,
)
from origin_ai_lab.secrets_store import SecretStoreError, get_secret, secret_exists, store_status


DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_QWEN_MODEL = "qwen3.7-max"
SECRET_DASHSCOPE_API_KEY = "dashscope_api_key"
SECRET_QWEN_BASE_URL = "qwen_base_url"
SECRET_QWEN_MODEL = "qwen_model"
SECRET_QWEN_ENABLE_THINKING = "qwen_enable_thinking"


class QwenPlannerError(RuntimeError):
    """Raised when the Qwen planner cannot return a valid intent."""


@dataclass(frozen=True)
class QwenConfig:
    api_key: str
    base_url: str = DEFAULT_QWEN_BASE_URL
    model: str = DEFAULT_QWEN_MODEL
    enable_thinking: bool = True
    timeout_seconds: int = 60
    key_source: str = "environment"

    @classmethod
    def from_env(cls) -> "QwenConfig | None":
        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        key_source = "environment"
        if not api_key:
            try:
                api_key = (get_secret(SECRET_DASHSCOPE_API_KEY) or "").strip()
                key_source = "local_store"
            except SecretStoreError:
                api_key = ""
        if not api_key:
            return None
        base_url = _env_or_secret("QWEN_BASE_URL", SECRET_QWEN_BASE_URL, DEFAULT_QWEN_BASE_URL)
        model = _env_or_secret("QWEN_MODEL", SECRET_QWEN_MODEL, DEFAULT_QWEN_MODEL)
        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            enable_thinking=_env_bool_or_secret("QWEN_ENABLE_THINKING", SECRET_QWEN_ENABLE_THINKING, True),
            key_source=key_source,
        )


def qwen_status() -> dict[str, Any]:
    config = QwenConfig.from_env()
    saved_key = False
    try:
        saved_key = secret_exists(SECRET_DASHSCOPE_API_KEY)
    except SecretStoreError:
        saved_key = False
    return {
        "configured": config is not None,
        "base_url": config.base_url if config else _env_or_secret("QWEN_BASE_URL", SECRET_QWEN_BASE_URL, DEFAULT_QWEN_BASE_URL),
        "model": config.model if config else _env_or_secret("QWEN_MODEL", SECRET_QWEN_MODEL, DEFAULT_QWEN_MODEL),
        "enable_thinking": config.enable_thinking if config else _env_bool_or_secret("QWEN_ENABLE_THINKING", SECRET_QWEN_ENABLE_THINKING, True),
        "key_env": "DASHSCOPE_API_KEY",
        "key_source": config.key_source if config else None,
        "saved_key": saved_key,
        "store": store_status(),
    }


def infer_requirement_with_qwen(
    raw_text: str,
    profile: DatasetProfile | None,
    config: QwenConfig | None = None,
) -> RequirementIntent:
    active_config = config or QwenConfig.from_env()
    if active_config is None:
        raise QwenPlannerError("DASHSCOPE_API_KEY is not configured.")

    payload = {
        "model": active_config.model,
        "messages": [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": _user_prompt(raw_text, profile)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "enable_thinking": active_config.enable_thinking,
    }
    response = _post_chat_completion(active_config, payload)
    content = response["choices"][0]["message"]["content"]
    data = _parse_json_content(content)
    return _intent_from_model_json(raw_text, data, profile, active_config.model)


def _post_chat_completion(config: QwenConfig, payload: dict[str, Any]) -> dict[str, Any]:
    url = config.base_url.rstrip("/") + "/chat/completions"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
                body = response.read().decode("utf-8")
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise QwenPlannerError(f"Qwen HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            if attempt == 2:
                raise QwenPlannerError(f"Qwen request failed: {exc.reason}") from exc
            time.sleep(1.0 + attempt)

    parsed = json.loads(body)
    if not parsed.get("choices"):
        raise QwenPlannerError("Qwen response has no choices.")
    return parsed


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL)
        if match:
            text = match.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise QwenPlannerError("Qwen did not return a JSON object.")
    return data


def _intent_from_model_json(
    raw_text: str,
    data: dict[str, Any],
    profile: DatasetProfile | None,
    model: str,
) -> RequirementIntent:
    questions = [
        ClarifyingQuestion(
            field=str(item.get("field", "unknown")),
            question=str(item.get("question", "")),
            options=tuple(str(option) for option in item.get("options", []) if option is not None),
        )
        for item in data.get("clarifying_questions", [])
        if isinstance(item, dict)
    ]
    assumptions = [str(item) for item in data.get("assumptions", []) if item is not None]
    assumptions.insert(0, f"Planner: qwen ({model}).")

    x_column = _valid_column_or_none(data.get("x_column"), profile)
    y_column = _valid_column_or_none(data.get("y_column"), profile)
    group_column = _valid_column_or_none(data.get("group_column"), profile, numeric_only=False)
    if profile is not None:
        existing = {column.name for column in profile.columns}
        for field, value in (
            ("x_column", data.get("x_column")),
            ("y_column", data.get("y_column")),
            ("group_column", data.get("group_column")),
        ):
            if value and str(value) not in existing:
                questions.append(
                    ClarifyingQuestion(
                        field=field,
                        question=f"模型选择了不存在的列 {value!r}，请确认要使用哪一列。",
                        options=tuple(column.name for column in profile.columns),
                    )
                )

    style = data.get("style") if isinstance(data.get("style"), dict) else {}
    output_formats = tuple(str(item).lower() for item in data.get("output_formats", []) if item is not None)
    kind = _enum_value(IntentKind, data.get("kind"), IntentKind.UNKNOWN)
    plot_kind = _enum_value(PlotKind, data.get("plot_kind"), PlotKind.AUTO)
    task_type = _enum_value(TaskType, data.get("task_type"), TaskType.PLOT_XY)
    if kind in {IntentKind.CREATE_PLOT, IntentKind.MODIFY_PLOT} and plot_kind != PlotKind.AUTO:
        task_type = TaskType.PLOT_XY

    questions = _drop_non_blocking_questions(questions, kind, plot_kind, x_column, y_column)

    return RequirementIntent(
        raw_text=raw_text.strip(),
        kind=kind,
        confidence=float(data.get("confidence", 0.8)),
        task_type=task_type,
        plot_kind=plot_kind,
        x_column=x_column,
        y_column=y_column,
        group_column=group_column,
        style=_normalize_style(style),
        output_formats=output_formats,
        assumptions=tuple(assumptions),
        clarifying_questions=tuple(questions),
    )


def _valid_column_or_none(value: Any, profile: DatasetProfile | None, numeric_only: bool = False) -> str | None:
    if value is None or value == "":
        return None
    column = str(value)
    if profile is None:
        return column
    columns = profile.numeric_columns() if numeric_only else [item.name for item in profile.columns]
    existing = set(columns)
    return column if column in existing else None


def _enum_value(enum_type: type[Any], value: Any, default: Any) -> Any:
    try:
        return enum_type(str(value))
    except Exception:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _normalize_style(style: dict[Any, Any]) -> dict[str, str]:
    raw = {str(key): str(value) for key, value in style.items()}
    normalized: dict[str, str] = {}
    if raw.get("color"):
        normalized["color"] = raw["color"]
    mark = raw.get("mark")
    if mark in {"scatter", "circle", "dot"}:
        normalized["mark"] = "point"
    elif mark in {"point", "line", "bar"}:
        normalized["mark"] = mark
    weight = raw.get("weight")
    if weight in {"bold", "heavy", "thick"}:
        normalized["weight"] = weight
    return normalized


def _drop_non_blocking_questions(
    questions: list[ClarifyingQuestion],
    kind: IntentKind,
    plot_kind: PlotKind,
    x_column: str | None,
    y_column: str | None,
) -> list[ClarifyingQuestion]:
    if kind not in {IntentKind.CREATE_PLOT, IntentKind.MODIFY_PLOT}:
        return questions
    ready_xy = plot_kind in {PlotKind.SCATTER, PlotKind.LINE, PlotKind.BAR} and bool(x_column and y_column)
    ready_histogram = plot_kind == PlotKind.HISTOGRAM and bool(y_column)
    if not (ready_xy or ready_histogram):
        return questions
    blocking_fields = {"dataset", "columns", "x_column", "y_column", "plot_kind", "histogram_column"}
    return [question for question in questions if question.field in blocking_fields and not _field_already_resolved(question.field, x_column, y_column, plot_kind)]


def _field_already_resolved(field: str, x_column: str | None, y_column: str | None, plot_kind: PlotKind) -> bool:
    if field == "x_column" and x_column:
        return True
    if field in {"y_column", "histogram_column"} and y_column:
        return True
    if field == "plot_kind" and plot_kind != PlotKind.AUTO:
        return True
    if field == "columns" and (x_column or y_column):
        return True
    return False


def _env_or_secret(env_name: str, secret_name: str, default: str) -> str:
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return env_value
    try:
        secret_value = get_secret(secret_name)
    except SecretStoreError:
        secret_value = None
    return (secret_value or default).strip() or default


def _env_bool_or_secret(env_name: str, secret_name: str, default: bool) -> bool:
    env_value = os.getenv(env_name)
    if env_value is not None:
        return env_value.strip().lower() not in {"0", "false", "no", "off"}
    try:
        secret_value = get_secret(secret_name)
    except SecretStoreError:
        secret_value = None
    if secret_value is None:
        return default
    return secret_value.strip().lower() not in {"0", "false", "no", "off"}


def _system_prompt() -> str:
    return """
You are the intent planner for Origin AI Lab, a scientific plotting assistant.
Return only a JSON object. Do not call tools and do not explain outside JSON.

Schema:
{
  "kind": "create_plot | modify_plot | analyze | export | unknown",
  "confidence": 0.0,
  "task_type": "describe | regression | plot_xy",
  "plot_kind": "auto | scatter | line | bar | histogram",
  "x_column": "column name or null",
  "y_column": "column name or null",
  "group_column": "group/color/facet column name or null",
  "style": {"color": "optional", "mark": "optional", "weight": "optional"},
  "output_formats": ["png", "svg", "pdf", "opju"],
  "assumptions": ["short assumption"],
  "clarifying_questions": [{"field": "field_name", "question": "question", "options": ["option"]}]
}

Rules:
- Use existing dataset column names exactly.
- Ask only blocking clarification questions.
- If there are exactly two numeric columns and the request is an XY plot, use them as x/y and record an assumption.
- For bar charts, the x column can be categorical and y can be numeric.
- For histograms, use one numeric value column as y_column and leave x_column null.
- If the user asks for grouping, multiple series, color by a column, or grouped bars, put the grouping column in group_column.
- The model only plans; it must never claim that Origin has already executed anything.
""".strip()


def _user_prompt(raw_text: str, profile: DatasetProfile | None) -> str:
    profile_json = profile.to_dict() if profile is not None else None
    return json.dumps(
        {
            "user_request": raw_text,
            "dataset_profile": profile_json,
        },
        ensure_ascii=False,
        indent=2,
    )
