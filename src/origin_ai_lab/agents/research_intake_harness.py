from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from origin_ai_lab.models import ClarifyingQuestion


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
            "ready_to_plan": self.ready_to_plan,
        }


THERMAL_INTAKE_QUESTIONS: tuple[IntakeQuestion, ...] = (
    IntakeQuestion(
        field="intended_use",
        prompt="这个结果主要拿来做什么？",
        why="同一个仿真，内部判断、实验方案、汇报展示和论文插图需要的证据强度不同。",
        priority="blocking_if_unclear",
        examples=("自己判断方向", "设计实验", "组会/项目展示", "论文插图", "对外验证报告"),
    ),
    IntakeQuestion(
        field="system_description",
        prompt="请用自然语言描述你脑子里的装置、样品或方案。",
        why="先完整保留用户语境，避免过早逼用户转成仿真软件术语。",
        priority="blocking",
        examples=("5W芯片贴在50mm铝板上", "一个圆柱电池包外面有风冷", "热源在薄板中心"),
    ),
    IntakeQuestion(
        field="geometry",
        prompt="你有没有几何文件，或者希望先用简化几何？",
        why="决定走 CAD/COMSOL 模板，还是先用 block/sphere/cylinder 简化模型。",
        priority="blocking_if_simulation",
        examples=("STEP/CAD文件", "已有COMSOL mph", "先用长方体简化", "我只有草图/照片"),
    ),
    IntakeQuestion(
        field="materials",
        prompt="已知材料有哪些？有没有热导率、密度、比热或材料表？",
        why="热仿真最容易被材料参数和温度适用范围拖偏。",
        priority="important",
        examples=("铝6061", "硅", "导热胶k=3 W/mK", "材料表在Excel里"),
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
        priority="blocking_if_simulation",
        examples=("自然对流25C", "风速8.5m/s", "底面固定80C", "四周绝热"),
    ),
    IntakeQuestion(
        field="quantities_of_interest",
        prompt="你最关心哪些结果？",
        why="决定要导出的数值、图像、动画和验证指标。",
        priority="important",
        examples=("最高温度", "热点位置", "热流路径", "某传感器点温度", "升温时间"),
    ),
    IntakeQuestion(
        field="constraints",
        prompt="有没有明确判据或约束？",
        why="没有判据就很难判断方案可不可行。",
        priority="important",
        examples=("不能超过80C", "温差小于5C", "10分钟内稳定", "尺寸不能超过20mm"),
    ),
    IntakeQuestion(
        field="comparison_or_sweep",
        prompt="是否要比较方案或扫描参数？",
        why="很多科研决策不是单点答案，而是方向和敏感性。",
        priority="optional",
        examples=("比较铜/铝", "功率1-10W", "风速0-3m/s", "接触热阻变化"),
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
        why="把仿真结果转成用户真正要用的交付物。",
        priority="important",
        examples=("简短判断", "实验方案", "汇报图", "论文插图", "完整报告", "动图"),
    ),
)


def build_research_work_order(goal: str, answers: dict[str, Any] | None = None) -> ResearchWorkOrder:
    answers = answers or {}
    normalized_goal = goal.lower()
    user_job = _infer_user_job(goal, answers)
    evidence_level = _infer_evidence_level(goal, answers, user_job)
    thick_context = _collect_thick_context(goal, answers)
    missing_blockers, questions = _blocking_questions(goal, answers, user_job)
    assumptions = _default_assumptions(answers, user_job)
    planned_outputs = _planned_outputs(user_job, evidence_level, answers)
    core_thread = _thin_core_thread(goal, user_job, evidence_level, answers, planned_outputs)

    if "热" in goal or "温度" in goal or "芯片" in goal or _infer_qoi(goal) == "maximum_temperature" or "thermal" in normalized_goal:
        thick_context["domain"] = "thermal_simulation"
    else:
        thick_context["domain"] = "scientific_analysis"

    return ResearchWorkOrder(
        raw_goal=goal,
        user_job=user_job,
        evidence_level=evidence_level,
        thick_context=thick_context,
        core_thread=core_thread,
        assumptions=tuple(assumptions),
        planned_outputs=tuple(planned_outputs),
        missing_blockers=tuple(missing_blockers),
        next_questions=tuple(questions),
    )


def intake_question_bank() -> list[dict[str, Any]]:
    return [question.to_dict() for question in THERMAL_INTAKE_QUESTIONS]


def _infer_user_job(goal: str, answers: dict[str, Any]) -> str:
    intended = str(answers.get("intended_use") or answers.get("output_format") or "").lower()
    text = f"{goal} {intended}".lower()
    if any(keyword in text for keyword in ("论文", "paper", "manuscript", "插图", "publication")):
        return "paper_evidence"
    if any(keyword in text for keyword in ("汇报", "展示", "presentation", "方案说明", "答辩")):
        return "presentation"
    if any(keyword in text for keyword in ("实验方案", "设计实验", "传感器", "thermocouple", "probe")):
        return "experiment_planning"
    if any(keyword in text for keyword in ("验证", "validation", "benchmark", "对外", "审稿", "可信")):
        return "validation_package"
    if any(keyword in text for keyword in ("可行", "会不会", "能不能", "判断", "estimate", "screen")):
        return "feasibility_screening"
    return "exploratory_analysis"


def _infer_evidence_level(goal: str, answers: dict[str, Any], user_job: str) -> str:
    explicit = str(answers.get("evidence_level") or "").strip()
    if explicit:
        return explicit
    if user_job in {"paper_evidence", "validation_package"}:
        return "publication_or_external_claim"
    if user_job in {"presentation", "experiment_planning"}:
        return "decision_support"
    if user_job == "feasibility_screening":
        return "quick_screening"
    return "scoping"


def _collect_thick_context(goal: str, answers: dict[str, Any]) -> dict[str, Any]:
    context: dict[str, Any] = {"goal_text": goal, "provided_fields": sorted(answers)}
    for question in THERMAL_INTAKE_QUESTIONS:
        value = answers.get(question.field)
        if value not in (None, "", [], {}):
            context[question.field] = value
    extra = {key: value for key, value in answers.items() if key not in {q.field for q in THERMAL_INTAKE_QUESTIONS}}
    if extra:
        context["extra_user_context"] = extra
    return context


def _blocking_questions(
    goal: str,
    answers: dict[str, Any],
    user_job: str,
) -> tuple[list[str], list[ClarifyingQuestion]]:
    missing: list[str] = []
    questions: list[ClarifyingQuestion] = []
    needs_simulation = user_job != "presentation" or _mentions_simulation(goal)

    if not _has_any(answers, "system_description") and len(goal.strip()) < 16:
        missing.append("system_description")
        questions.append(
            ClarifyingQuestion(
                field="system_description",
                question="请先用一句话描述要研究的装置、样品或热方案。",
                options=("芯片/封装散热", "薄板/块体导热", "流体/风冷换热"),
            )
        )

    if needs_simulation and not (_has_any(answers, "geometry") or _has_geometry_hint(goal)):
        missing.append("geometry")
        questions.append(
            ClarifyingQuestion(
                field="geometry",
                question="你有几何文件，还是先用简化几何开始？",
                options=("先用简化几何", "我有CAD/COMSOL文件", "我只有草图/照片"),
            )
        )

    if needs_simulation and not (_has_any(answers, "heat_sources") or _has_heat_source_hint(goal)):
        missing.append("heat_sources")
        questions.append(
            ClarifyingQuestion(
                field="heat_sources",
                question="热源大概是多少，作用在哪里？",
                options=("总功率W", "热流密度W/m2", "暂时未知，先估算"),
            )
        )

    if not _has_any(answers, "intended_use", "output_format"):
        questions.append(
            ClarifyingQuestion(
                field="intended_use",
                question="这个结果主要准备用来做什么？",
                options=("自己判断方向", "实验方案", "展示/论文图"),
            )
        )

    return missing, questions[:3]


def _default_assumptions(answers: dict[str, Any], user_job: str) -> list[str]:
    assumptions: list[str] = []
    if not _has_any(answers, "geometry"):
        assumptions.append("If no geometry file is supplied, start from a simplified primitive model.")
    if not _has_any(answers, "cooling_boundaries"):
        assumptions.append("If cooling conditions are unknown, start with a declared default and mark it as a sensitivity parameter.")
    if user_job in {"paper_evidence", "validation_package"}:
        assumptions.append("External-facing results require validation evidence before conclusions are accepted.")
    return assumptions


def _planned_outputs(user_job: str, evidence_level: str, answers: dict[str, Any]) -> list[str]:
    output = str(answers.get("output_format") or "").lower()
    outputs_by_job = {
        "feasibility_screening": ["short_decision_memo", "assumptions", "risk_flags", "next_experiment_suggestions"],
        "experiment_planning": ["experiment_plan", "parameter_matrix", "probe_placement_suggestions", "expected_ranges"],
        "presentation": ["annotated_figures", "temperature_visual_package", "talking_points"],
        "paper_evidence": ["paper_figures", "methods_text", "plot_data_csv", "limitations"],
        "validation_package": ["vv_report", "golden_case_comparison", "mesh_convergence_plan", "evidence_manifest"],
        "exploratory_analysis": ["scoping_memo", "candidate_model_paths", "blocking_questions"],
    }
    planned = list(outputs_by_job.get(user_job, outputs_by_job["exploratory_analysis"]))
    if "动图" in output or "animation" in output or "gif" in output:
        planned.append("animation_package")
    if evidence_level == "publication_or_external_claim" and "evidence_manifest" not in planned:
        planned.append("evidence_manifest")
    return planned


def _thin_core_thread(
    goal: str,
    user_job: str,
    evidence_level: str,
    answers: dict[str, Any],
    planned_outputs: list[str],
) -> dict[str, Any]:
    return {
        "one_sentence_goal": goal.strip(),
        "user_job": user_job,
        "evidence_level": evidence_level,
        "primary_system": answers.get("system_description") or goal.strip(),
        "primary_qoi": answers.get("quantities_of_interest") or _infer_qoi(goal),
        "decision_criterion": answers.get("constraints") or _infer_constraint(goal),
        "preferred_outputs": planned_outputs,
    }


def _infer_qoi(goal: str) -> str:
    text = goal.lower()
    if any(keyword in text for keyword in ("最高温", "温度", "超过", "max temperature", "overheat", "过热")):
        return "maximum_temperature"
    if any(keyword in text for keyword in ("热流", "heat flux", "路径")):
        return "heat_flow_path"
    if any(keyword in text for keyword in ("时间", "升温", "冷却", "transient")):
        return "temperature_time_history"
    return "to_be_confirmed"


def _infer_constraint(goal: str) -> str:
    if "超过" in goal or "不能" in goal or "<" in goal or ">" in goal:
        return "mentioned_in_goal_text"
    return "not_declared"


def _has_any(answers: dict[str, Any], *fields: str) -> bool:
    return any(answers.get(field) not in (None, "", [], {}) for field in fields)


def _mentions_simulation(goal: str) -> bool:
    text = goal.lower()
    return any(keyword in text for keyword in ("仿真", "模拟", "comsol", "simulate", "simulation"))


def _has_geometry_hint(goal: str) -> bool:
    text = goal.lower()
    return any(keyword in text for keyword in ("长方体", "圆柱", "球", "板", "片", "cad", "step", "stl", "mm", "cm", "m "))


def _has_heat_source_hint(goal: str) -> bool:
    text = goal.lower()
    return any(keyword in text for keyword in ("w", "瓦", "功率", "热源", "heat source", "heat flux"))
