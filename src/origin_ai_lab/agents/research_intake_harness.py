from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from origin_ai_lab.models import ClarifyingQuestion


SOURCE_USER = "user"
SOURCE_FILE = "file"
SOURCE_DEFAULT = "default"
SOURCE_LITERATURE = "literature"
SOURCE_TOOL_OUTPUT = "tool_output"

KNOWN_SOURCES = {
    SOURCE_USER,
    SOURCE_FILE,
    SOURCE_DEFAULT,
    SOURCE_LITERATURE,
    SOURCE_TOOL_OUTPUT,
}


@dataclass(frozen=True)
class IntakeQuestion:
    field: str
    prompt: str
    why: str
    priority: str = "optional"
    examples: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "prompt": self.prompt,
            "why": self.why,
            "priority": self.priority,
            "examples": list(self.examples),
        }


@dataclass(frozen=True)
class EvidenceTrace:
    field: str
    source: str
    value: Any
    note: str = ""
    confidence: str = "declared"
    source_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        source = self.source if self.source in KNOWN_SOURCES else SOURCE_TOOL_OUTPUT
        return {
            "field": self.field,
            "source": source,
            "value": _json_safe(self.value),
            "note": self.note,
            "confidence": self.confidence,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True)
class ResearchWorkOrder:
    raw_goal: str
    user_job: str
    evidence_level: str
    thick_context: dict[str, Any] = field(default_factory=dict)
    core_thread: dict[str, Any] = field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    planned_outputs: tuple[str, ...] = ()
    missing_blockers: tuple[str, ...] = ()
    next_questions: tuple[ClarifyingQuestion, ...] = ()
    evidence_trace: tuple[EvidenceTrace, ...] = ()
    schema_version: str = "research-work-order/v1"

    @property
    def ready_to_plan(self) -> bool:
        return not self.missing_blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "raw_goal": self.raw_goal,
            "user_job": self.user_job,
            "evidence_level": self.evidence_level,
            "thick_context": self.thick_context,
            "core_thread": self.core_thread,
            "assumptions": list(self.assumptions),
            "planned_outputs": list(self.planned_outputs),
            "missing_blockers": list(self.missing_blockers),
            "next_questions": [question.to_dict() for question in self.next_questions],
            "evidence_trace": [item.to_dict() for item in self.evidence_trace],
            "ready_to_plan": self.ready_to_plan,
        }


THERMAL_INTAKE_QUESTIONS: tuple[IntakeQuestion, ...] = (
    IntakeQuestion(
        field="intended_use",
        prompt="这个结果主要准备用来做什么？",
        why="同一个科研目标，用于自己判断、实验方案、展示、论文插图或验证报告时，需要的证据强度不同。",
        priority="blocking_if_unclear",
        examples=("自己判断方向", "设计实验方案", "组会或项目展示", "论文插图", "验证报告"),
    ),
    IntakeQuestion(
        field="system_description",
        prompt="请用自然语言描述要研究的装置、样品、材料体系或数据对象。",
        why="先保留用户自己的语境，再压缩成内部任务，避免过早把需求翻译成软件术语。",
        priority="blocking",
        examples=("5W芯片贴在50mm铝板上", "圆柱电池包外面有风冷", "XRD数据需要做论文图"),
    ),
    IntakeQuestion(
        field="geometry",
        prompt="是否有几何文件，还是希望先用简化几何？",
        why="决定从 CAD/COMSOL 模板开始，还是先用 block/sphere/cylinder 等简化模型。",
        priority="blocking_if_simulation",
        examples=("STEP/CAD文件", "已有COMSOL mph", "先用长方体简化", "只有草图或照片"),
    ),
    IntakeQuestion(
        field="materials",
        prompt="已知材料有哪些？有没有热导率、密度、比热或材料表？",
        why="材料参数和适用温度范围会显著影响热仿真可信度。",
        priority="important",
        examples=("铝6061", "硅", "导热垫 k=3 W/mK", "材料表在Excel里"),
    ),
    IntakeQuestion(
        field="heat_sources",
        prompt="热从哪里来？功率、热流密度、发热区域和持续时间是什么？",
        why="热源大小和位置通常决定热点，是热仿真的主线变量。",
        priority="blocking_if_simulation",
        examples=("芯片5W", "中心圆斑1W", "边界热流1000 W/m2", "脉冲加热10s"),
    ),
    IntakeQuestion(
        field="cooling_boundaries",
        prompt="热怎么散出去？环境温度、风速、对流系数、固定温度或绝热面有哪些？",
        why="边界条件是热仿真可信度的第一大风险源。",
        priority="important",
        examples=("自然对流25C", "风速0.5m/s", "底面固定80C", "四周绝热"),
    ),
    IntakeQuestion(
        field="quantities_of_interest",
        prompt="你最关心哪些结果？",
        why="决定要导出的数值、图像、动画和验证指标。",
        priority="important",
        examples=("最高温度", "热点位置", "热流路径", "传感器点温度", "升温时间"),
    ),
    IntakeQuestion(
        field="constraints",
        prompt="有没有明确判据或约束？",
        why="没有判据就很难判断方案是否可行。",
        priority="important",
        examples=("不能超过80C", "温差小于5C", "10分钟内稳定", "尺寸不能超过20mm"),
    ),
    IntakeQuestion(
        field="comparison_or_sweep",
        prompt="是否要比较方案或扫描参数？",
        why="很多科研决策不是单点答案，而是方案、范围和敏感性。",
        priority="optional",
        examples=("比较铝和铜", "功率1-10W", "风速0-3m/s", "接触热阻变化"),
    ),
    IntakeQuestion(
        field="validation_data",
        prompt="有没有实验数据、手算结果、文献 benchmark 或历史样品可以对比？",
        why="决定结果能否从参考结论升级到可验证证据。",
        priority="optional",
        examples=("热电偶CSV", "红外图", "论文数据", "已有样品测试记录"),
    ),
    IntakeQuestion(
        field="output_format",
        prompt="你希望最后拿到什么？",
        why="把内部分析结果转成用户真正要用的交付物。",
        priority="important",
        examples=("简短判断", "实验方案", "汇报图", "论文插图", "完整报告", "动画"),
    ),
)


USER_JOB_LABELS: dict[str, str] = {
    "feasibility_screening": "自己判断",
    "experiment_planning": "实验方案",
    "presentation": "展示",
    "paper_figure": "论文插图",
    "validation_report": "验证报告",
    "exploratory_analysis": "探索分析",
}

QUESTION_FIELDS = {question.field for question in THERMAL_INTAKE_QUESTIONS}
INTERNAL_CONTEXT_FIELDS = {
    "files",
    "attachments",
    "file",
    "file_paths",
    "dataset",
    "dataset_path",
    "dataset_profile",
    "profile",
    "expected_output",
    "literature",
    "literature_refs",
    "tool_outputs",
}


def build_research_work_order(
    goal: str,
    answers: dict[str, Any] | None = None,
    files: list[Any] | tuple[Any, ...] | None = None,
) -> ResearchWorkOrder:
    answers = _normalize_answers(answers)
    if files is not None and "files" not in answers:
        answers["files"] = list(files)

    normalized_goal = _normalize_text(goal)
    file_context = _collect_file_context(answers)
    trace = _initial_trace(goal, answers, file_context)
    user_job = _infer_user_job(goal, answers)
    domain = _infer_domain(goal, answers, file_context)
    required_capabilities = _infer_required_capabilities(goal, answers, user_job, domain, file_context)
    evidence_level = _infer_evidence_level(goal, answers, user_job)
    planned_outputs = _planned_outputs(user_job, evidence_level, required_capabilities, answers)
    thick_context = _collect_thick_context(
        goal=goal,
        answers=answers,
        file_context=file_context,
        domain=domain,
        user_job=user_job,
        required_capabilities=required_capabilities,
    )
    missing_blockers, questions = _blocking_questions(
        goal=goal,
        answers=answers,
        user_job=user_job,
        domain=domain,
        required_capabilities=required_capabilities,
        file_context=file_context,
    )
    assumptions = _default_assumptions(answers, user_job, domain, required_capabilities, file_context)
    core_thread = _thin_core_thread(
        goal=goal,
        user_job=user_job,
        evidence_level=evidence_level,
        domain=domain,
        required_capabilities=required_capabilities,
        answers=answers,
        file_context=file_context,
        planned_outputs=planned_outputs,
        missing_blockers=missing_blockers,
    )

    trace.extend(
        [
            EvidenceTrace(
                field="user_job",
                source=SOURCE_TOOL_OUTPUT,
                value=user_job,
                note="Rule inference from user goal, intended use, and expected output.",
                confidence="inferred",
            ),
            EvidenceTrace(
                field="domain",
                source=SOURCE_TOOL_OUTPUT,
                value=domain,
                note="Rule inference from scientific keywords and file profile hints.",
                confidence="inferred",
            ),
            EvidenceTrace(
                field="required_capabilities",
                source=SOURCE_TOOL_OUTPUT,
                value=required_capabilities,
                note="Internal routing hint; not exposed as separate user modes.",
                confidence="inferred",
            ),
            EvidenceTrace(
                field="evidence_level",
                source=SOURCE_TOOL_OUTPUT,
                value=evidence_level,
                note="Evidence level follows intended use unless explicitly supplied.",
                confidence="inferred" if not _has_any(answers, "evidence_level") else "declared",
            ),
        ]
    )
    for assumption in assumptions:
        trace.append(
            EvidenceTrace(
                field="assumption",
                source=SOURCE_DEFAULT,
                value=assumption,
                note="Default assumption to make a first work order possible; must be validated before execution.",
                confidence="default",
            )
        )

    return ResearchWorkOrder(
        raw_goal=normalized_goal,
        user_job=user_job,
        evidence_level=evidence_level,
        thick_context=thick_context,
        core_thread=core_thread,
        assumptions=tuple(assumptions),
        planned_outputs=tuple(planned_outputs),
        missing_blockers=tuple(missing_blockers),
        next_questions=tuple(questions),
        evidence_trace=tuple(trace),
    )


def intake_question_bank() -> list[dict[str, Any]]:
    return [question.to_dict() for question in THERMAL_INTAKE_QUESTIONS]


def _normalize_answers(answers: dict[str, Any] | None) -> dict[str, Any]:
    if not answers:
        return {}
    return {str(key): value for key, value in answers.items() if value not in (None, "", [], {})}


def _initial_trace(goal: str, answers: dict[str, Any], file_context: list[dict[str, Any]]) -> list[EvidenceTrace]:
    trace: list[EvidenceTrace] = [
        EvidenceTrace(
            field="goal",
            source=SOURCE_USER,
            value=_normalize_text(goal),
            note="Raw natural-language goal supplied by the user.",
            confidence="declared",
        )
    ]
    for field in sorted(answers):
        if field in INTERNAL_CONTEXT_FIELDS:
            continue
        trace.append(
            EvidenceTrace(
                field=field,
                source=SOURCE_USER,
                value=answers[field],
                note="Structured intake answer supplied by the user or UI.",
                confidence="declared",
            )
        )
    for file_item in file_context:
        trace.append(
            EvidenceTrace(
                field="input_file",
                source=SOURCE_FILE,
                value=file_item,
                note="File context supplied to the single intake entry.",
                confidence="declared",
                source_ref=str(file_item.get("path") or file_item.get("name") or ""),
            )
        )
        if "profile" in file_item:
            trace.append(
                EvidenceTrace(
                    field="file_profile",
                    source=SOURCE_TOOL_OUTPUT,
                    value=file_item["profile"],
                    note="Lightweight table profile generated from the input file.",
                    confidence="derived",
                    source_ref=str(file_item.get("path") or file_item.get("name") or ""),
                )
            )
    for item in _as_list(answers.get("literature") or answers.get("literature_refs")):
        trace.append(
            EvidenceTrace(
                field="literature",
                source=SOURCE_LITERATURE,
                value=item,
                note="User-supplied literature or benchmark reference.",
                confidence="declared",
            )
        )
    for item in _as_list(answers.get("tool_outputs")):
        trace.append(
            EvidenceTrace(
                field="tool_output",
                source=SOURCE_TOOL_OUTPUT,
                value=item,
                note="Prior tool output supplied as context.",
                confidence="derived",
            )
        )
    return trace


def _collect_file_context(answers: dict[str, Any]) -> list[dict[str, Any]]:
    raw_items: list[Any] = []
    for field in ("files", "attachments", "file_paths"):
        raw_items.extend(_as_list(answers.get(field)))
    for field in ("file", "dataset", "dataset_path"):
        if _has_any(answers, field):
            raw_items.append(answers[field])

    file_context: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        item = _normalize_file_item(raw_item, answers)
        key = str(item.get("path") or item.get("name") or item)
        if key in seen:
            continue
        seen.add(key)
        file_context.append(item)
    if not file_context and _has_any(answers, "dataset_profile", "profile"):
        file_context.append(
            {
                "kind": "dataset",
                "role": "analysis_input",
                "profile": _summarize_profile(answers.get("dataset_profile") or answers.get("profile")),
            }
        )
    return file_context


def _normalize_file_item(raw_item: Any, answers: dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw_item, dict):
        item = dict(raw_item)
    else:
        item = {"path": str(raw_item)}
    item.setdefault("kind", _infer_file_kind(item))
    item.setdefault("role", "analysis_input")
    profile = item.get("profile")
    if profile is None:
        profile = answers.get("dataset_profile") or answers.get("profile")
    if profile is not None:
        item["profile"] = _summarize_profile(profile)
    return item


def _infer_file_kind(item: dict[str, Any]) -> str:
    path = str(item.get("path") or item.get("name") or "").lower()
    if path.endswith((".csv", ".tsv", ".txt", ".xlsx", ".xls")):
        return "dataset"
    if path.endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")):
        return "image"
    if path.endswith((".step", ".stp", ".stl", ".igs", ".iges", ".mph")):
        return "geometry_or_model"
    if path.endswith((".pdf", ".docx", ".md")):
        return "reference_or_report"
    return "file"


def _summarize_profile(profile: Any) -> dict[str, Any]:
    if hasattr(profile, "to_dict"):
        profile = profile.to_dict()
    if not isinstance(profile, dict):
        return {"raw_profile": _json_safe(profile)}
    columns = profile.get("columns") if isinstance(profile.get("columns"), list) else []
    return {
        "path": profile.get("path"),
        "row_count": profile.get("row_count"),
        "columns": [
            {
                "name": column.get("name"),
                "numeric_ratio": column.get("numeric_ratio"),
                "examples": column.get("examples", [])[:3] if isinstance(column.get("examples"), list) else [],
            }
            for column in columns
            if isinstance(column, dict)
        ][:24],
    }


def _infer_user_job(goal: str, answers: dict[str, Any]) -> str:
    intended = " ".join(
        str(value)
        for value in (
            answers.get("intended_use"),
            answers.get("output_format"),
            answers.get("expected_output"),
            answers.get("purpose"),
        )
        if value
    )
    text = _search_text(goal, intended)
    if _contains_any(text, ("验证报告", "验证", "校验", "benchmark", "v&v", "对外", "审核", "可信", "复现")):
        return "validation_report"
    if _contains_any(text, ("论文插图", "论文图", "论文", "投稿", "publication", "paper", "manuscript", "methods", "图注")):
        return "paper_figure"
    if _contains_any(text, ("实验方案", "设计实验", "实验设计", "测点", "传感器", "探针", "热电偶", "doe", "probe")):
        return "experiment_planning"
    if _contains_any(text, ("展示", "汇报", "组会", "答辩", "ppt", "presentation", "poster", "海报")):
        return "presentation"
    if _contains_any(text, ("自己判断", "判断方向", "可行", "会不会", "能不能", "粗估", "快速判断", "estimate", "screen")):
        return "feasibility_screening"
    return "exploratory_analysis"


def _infer_evidence_level(goal: str, answers: dict[str, Any], user_job: str) -> str:
    explicit = _optional_text(answers.get("evidence_level"))
    if explicit:
        return explicit
    if user_job in {"paper_figure", "validation_report"}:
        return "publication_or_external_claim"
    if user_job in {"presentation", "experiment_planning"}:
        return "decision_support"
    if user_job == "feasibility_screening":
        return "quick_screening"
    if _contains_any(_search_text(goal), ("验证", "benchmark", "误差", "uncertainty")):
        return "decision_support"
    return "scoping"


def _infer_domain(goal: str, answers: dict[str, Any], file_context: list[dict[str, Any]]) -> str:
    text = _search_text(goal, *(str(value) for value in answers.values()))
    if _contains_any(
        text,
        (
            "热",
            "温度",
            "散热",
            "导热",
            "对流",
            "冷却",
            "芯片",
            "功率",
            "升温",
            "thermal",
            "temperature",
            "heat",
            "cooling",
            "comsol",
        ),
    ):
        return "thermal_simulation"
    if _contains_any(text, ("xrd", "raman", "eis", "nyquist", "dsc", "tga", "光谱", "衍射", "origin")):
        return "materials_data_analysis"
    if any(item.get("kind") == "dataset" for item in file_context):
        return "scientific_data_analysis"
    if any(item.get("kind") == "geometry_or_model" for item in file_context):
        return "simulation_modeling"
    return "scientific_analysis"


def _infer_required_capabilities(
    goal: str,
    answers: dict[str, Any],
    user_job: str,
    domain: str,
    file_context: list[dict[str, Any]],
) -> list[str]:
    text = _search_text(goal, *(str(value) for value in answers.values()))
    capabilities: list[str] = []
    if domain in {"thermal_simulation", "simulation_modeling"} or _contains_any(
        text,
        ("仿真", "模拟", "comsol", "simulation", "simulate", "有限元", "温度场"),
    ):
        capabilities.append("simulation")
    if _contains_any(
        text,
        ("画图", "绘图", "出图", "图谱", "曲线", "散点", "柱状图", "插图", "figure", "plot", "origin", "png", "svg", "pdf"),
    ) or user_job in {"presentation", "paper_figure"} or any(item.get("kind") == "dataset" for item in file_context):
        capabilities.append("plotting")
    if _contains_any(text, ("报告", "方案", "memo", "report", "methods", "说明", "结论")) or user_job in {
        "experiment_planning",
        "validation_report",
        "feasibility_screening",
    }:
        capabilities.append("reporting")
    if user_job == "validation_report" or _contains_any(text, ("验证", "校验", "benchmark", "误差", "不确定度", "复现", "可信")):
        capabilities.append("validation")
    if not capabilities:
        capabilities.append("analysis")
    return _dedupe(capabilities)


def _collect_thick_context(
    goal: str,
    answers: dict[str, Any],
    file_context: list[dict[str, Any]],
    domain: str,
    user_job: str,
    required_capabilities: list[str],
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "goal_text": _normalize_text(goal),
        "domain": domain,
        "user_job": user_job,
        "user_job_label": USER_JOB_LABELS.get(user_job, user_job),
        "required_capabilities": list(required_capabilities),
        "provided_fields": sorted(
            field
            for field, value in answers.items()
            if value not in (None, "", [], {}) and field not in INTERNAL_CONTEXT_FIELDS
        ),
        "input_files": file_context,
        "evidence_source_summary": {
            SOURCE_USER: True,
            SOURCE_FILE: bool(file_context),
            SOURCE_DEFAULT: True,
            SOURCE_LITERATURE: bool(answers.get("literature") or answers.get("literature_refs")),
            SOURCE_TOOL_OUTPUT: True,
        },
    }
    for question in THERMAL_INTAKE_QUESTIONS:
        value = answers.get(question.field)
        if value not in (None, "", [], {}):
            context[question.field] = value
    expected = answers.get("expected_output")
    if expected and "output_format" not in context:
        context["output_format"] = expected

    extra = {
        key: value
        for key, value in answers.items()
        if key not in QUESTION_FIELDS and key not in INTERNAL_CONTEXT_FIELDS and value not in (None, "", [], {})
    }
    if extra:
        context["extra_user_context"] = extra
    return context


def _blocking_questions(
    goal: str,
    answers: dict[str, Any],
    user_job: str,
    domain: str,
    required_capabilities: list[str],
    file_context: list[dict[str, Any]],
) -> tuple[list[str], list[ClarifyingQuestion]]:
    missing: list[str] = []
    questions: list[ClarifyingQuestion] = []
    goal_text = _normalize_text(goal)
    text = _search_text(goal_text, *(str(value) for value in answers.values()))
    needs_simulation = "simulation" in required_capabilities
    needs_plotting = "plotting" in required_capabilities

    if not _has_any(answers, "system_description") and not _has_system_hint(text, file_context):
        missing.append("system_description")
        questions.append(
            ClarifyingQuestion(
                field="system_description",
                question="请先用一句话描述要研究的装置、样品、材料体系或数据对象。",
                options=("芯片/封装散热", "材料测试数据", "实验装置或样品", "已有图或报告"),
            )
        )

    if not _has_any(answers, "intended_use", "output_format", "expected_output") and user_job == "exploratory_analysis":
        missing.append("intended_use")
        questions.append(
            ClarifyingQuestion(
                field="intended_use",
                question="这个结果准备用来做什么？",
                options=("自己判断方向", "实验方案", "展示", "论文插图", "验证报告"),
            )
        )

    if needs_simulation and not (_has_any(answers, "geometry") or _has_geometry_hint(text) or _has_file_kind(file_context, "geometry_or_model")):
        missing.append("geometry")
        questions.append(
            ClarifyingQuestion(
                field="geometry",
                question="有几何文件，还是先从简化几何开始？",
                options=("先用简化几何", "我有CAD/COMSOL文件", "只有草图或照片"),
            )
        )

    if needs_simulation and not (_has_any(answers, "heat_sources") or _has_heat_source_hint(text)):
        missing.append("heat_sources")
        questions.append(
            ClarifyingQuestion(
                field="heat_sources",
                question="热源大概是多少，作用在哪里？",
                options=("总功率W", "热流密度W/m2", "暂时未知，先估算"),
            )
        )

    if needs_plotting and not (_has_file_kind(file_context, "dataset") or _has_any(answers, "dataset_profile", "profile")):
        if _contains_any(text, ("画图", "绘图", "图谱", "曲线", "plot", "figure", "origin")):
            missing.append("input_files")
            questions.append(
                ClarifyingQuestion(
                    field="input_files",
                    question="需要画图或分析的话，请提供数据文件，或说明先用哪个样例数据。",
                    options=("CSV/Excel数据", "已有Origin项目", "先不画图，只规划"),
                )
            )

    if needs_simulation and not (_has_any(answers, "cooling_boundaries") or _has_boundary_hint(text)):
        questions.append(
            ClarifyingQuestion(
                field="cooling_boundaries",
                question="散热边界先按什么处理？",
                options=("自然对流25C", "给定风速/对流系数", "固定温度或绝热面"),
            )
        )

    return _dedupe(missing), questions[:3]


def _default_assumptions(
    answers: dict[str, Any],
    user_job: str,
    domain: str,
    required_capabilities: list[str],
    file_context: list[dict[str, Any]],
) -> list[str]:
    assumptions: list[str] = []
    if "simulation" in required_capabilities and not _has_file_kind(file_context, "geometry_or_model") and not _has_any(answers, "geometry"):
        assumptions.append("If no geometry/model file is supplied, start from a simplified geometry and record the simplification.")
    if domain == "thermal_simulation" and not _has_any(answers, "materials"):
        assumptions.append("Unknown material properties must be declared as placeholders and replaced with measured or literature values before execution.")
    if domain == "thermal_simulation" and not _has_any(answers, "cooling_boundaries"):
        assumptions.append("If cooling conditions are unknown, start with a declared default boundary and mark it as a sensitivity parameter.")
    if user_job in {"paper_figure", "validation_report"}:
        assumptions.append("External-facing results require validation evidence and an evidence manifest before conclusions are accepted.")
    if user_job == "feasibility_screening":
        assumptions.append("Quick screening results are decision support only; they are not accepted scientific evidence until validated.")
    return _dedupe(assumptions)


def _planned_outputs(
    user_job: str,
    evidence_level: str,
    required_capabilities: list[str],
    answers: dict[str, Any],
) -> list[str]:
    output_text = _search_text(str(answers.get("output_format") or ""), str(answers.get("expected_output") or ""))
    outputs_by_job = {
        "feasibility_screening": ["short_decision_memo", "assumptions", "risk_flags", "next_experiment_suggestions"],
        "experiment_planning": ["experiment_plan", "parameter_matrix", "measurement_plan", "expected_ranges"],
        "presentation": ["annotated_figures", "presentation_figure_set", "talking_points"],
        "paper_figure": ["paper_figures", "plot_data_csv", "methods_notes", "limitations"],
        "validation_report": ["validation_report", "evidence_manifest", "numerical_checks", "benchmark_comparison"],
        "exploratory_analysis": ["research_work_order", "candidate_workflow", "blocking_questions"],
    }
    planned = list(outputs_by_job.get(user_job, outputs_by_job["exploratory_analysis"]))
    if "simulation" in required_capabilities:
        planned.extend(["simulation_plan", "parameter_table"])
    if "plotting" in required_capabilities:
        planned.extend(["plot_spec", "figure_export_plan"])
    if "reporting" in required_capabilities and "report_outline" not in planned:
        planned.append("report_outline")
    if "validation" in required_capabilities and "evidence_manifest" not in planned:
        planned.append("evidence_manifest")
    if _contains_any(output_text, ("动画", "动图", "animation", "gif", "mp4")):
        planned.append("animation_package")
    if evidence_level == "publication_or_external_claim" and "limitations" not in planned:
        planned.append("limitations")
    return _dedupe(planned)


def _thin_core_thread(
    goal: str,
    user_job: str,
    evidence_level: str,
    domain: str,
    required_capabilities: list[str],
    answers: dict[str, Any],
    file_context: list[dict[str, Any]],
    planned_outputs: list[str],
    missing_blockers: list[str],
) -> dict[str, Any]:
    known_parameters = _known_parameter_fields(answers)
    return {
        "one_sentence_goal": _normalize_text(goal),
        "user_job": user_job,
        "user_job_label": USER_JOB_LABELS.get(user_job, user_job),
        "evidence_level": evidence_level,
        "domain": domain,
        "required_capabilities": list(required_capabilities),
        "primary_system": answers.get("system_description") or _infer_primary_system(goal, file_context),
        "primary_qoi": answers.get("quantities_of_interest") or _infer_qoi(goal, domain),
        "decision_criterion": answers.get("constraints") or _infer_constraint(goal),
        "known_parameters": known_parameters,
        "input_files": [
            {
                "path": item.get("path"),
                "kind": item.get("kind"),
                "role": item.get("role"),
            }
            for item in file_context
        ],
        "preferred_outputs": planned_outputs,
        "ready_state": "ready_to_plan" if not missing_blockers else "needs_clarification",
    }


def _known_parameter_fields(answers: dict[str, Any]) -> dict[str, Any]:
    fields = ("geometry", "materials", "heat_sources", "cooling_boundaries", "constraints", "comparison_or_sweep", "validation_data")
    return {field: answers[field] for field in fields if _has_any(answers, field)}


def _infer_primary_system(goal: str, file_context: list[dict[str, Any]]) -> str:
    text = _normalize_text(goal)
    if len(text) >= 12 and not _is_generic_request(text):
        return text
    if file_context:
        names = [str(item.get("path") or item.get("name") or item.get("kind")) for item in file_context]
        return ", ".join(names)
    return "to_be_confirmed"


def _infer_qoi(goal: str, domain: str = "scientific_analysis") -> str:
    text = _search_text(goal)
    if _contains_any(text, ("最高温", "最大温", "温度", "超过", "过热", "max temperature", "overheat")):
        return "maximum_temperature"
    if _contains_any(text, ("热流", "热通量", "heat flux", "路径", "热阻")):
        return "heat_flow_path"
    if _contains_any(text, ("时间", "升温", "冷却", "瞬态", "transient", "time history")):
        return "time_history"
    if _contains_any(text, ("峰", "peak", "强度", "intensity", "xrd", "raman")):
        return "peak_or_spectrum_features"
    if _contains_any(text, ("拟合", "回归", "斜率", "相关", "fit", "regression")):
        return "fit_or_trend"
    if domain == "thermal_simulation":
        return "thermal_risk"
    return "to_be_confirmed"


def _infer_constraint(goal: str) -> str:
    text = _search_text(goal)
    if _contains_any(text, ("不能", "不超过", "小于", "大于", "低于", "高于", "below", "under", "over", "<", ">")):
        return "mentioned_in_goal_text"
    return "not_declared"


def _has_any(answers: dict[str, Any], *fields: str) -> bool:
    return any(answers.get(field) not in (None, "", [], {}) for field in fields)


def _has_file_kind(file_context: list[dict[str, Any]], kind: str) -> bool:
    return any(item.get("kind") == kind for item in file_context)


def _has_system_hint(text: str, file_context: list[dict[str, Any]]) -> bool:
    if file_context:
        return True
    if len(text.strip()) < 10 or _is_generic_request(text):
        return False
    return _contains_any(
        text,
        (
            "芯片",
            "铝板",
            "电池",
            "样品",
            "材料",
            "xrd",
            "raman",
            "eis",
            "数据",
            "plate",
            "chip",
            "battery",
            "sample",
            "device",
        ),
    )


def _is_generic_request(text: str) -> bool:
    normalized = _search_text(text).strip()
    return normalized in {"热仿真", "仿真", "画图", "分析", "做报告", "simulation", "plot", "analysis", "report"}


def _has_geometry_hint(text: str) -> bool:
    return _contains_any(
        text,
        (
            "长方体",
            "圆柱",
            "球",
            "板",
            "薄片",
            "尺寸",
            "几何",
            "cad",
            "step",
            "stl",
            "mm",
            "cm",
            "m ",
            "plate",
            "cylinder",
            "block",
        ),
    )


def _has_heat_source_hint(text: str) -> bool:
    return _contains_any(text, ("w", "瓦", "功率", "热源", "发热", "heat source", "heat flux", "power"))


def _has_boundary_hint(text: str) -> bool:
    return _contains_any(
        text,
        ("自然对流", "风冷", "水冷", "环境", "绝热", "固定温度", "风速", "convection", "ambient", "cooling", "insulated"),
    )


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _search_text(*parts: str) -> str:
    return " ".join(_normalize_text(part).lower() for part in parts if part)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _optional_text(value: Any) -> str | None:
    text = _normalize_text(value)
    return text or None


def _as_list(value: Any) -> list[Any]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
