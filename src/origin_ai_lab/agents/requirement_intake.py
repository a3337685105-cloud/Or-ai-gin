from __future__ import annotations

from origin_ai_lab.models import (
    ClarifyingQuestion,
    DatasetProfile,
    IntentKind,
    PlotKind,
    RequirementIntent,
    TaskType,
)


PLOT_KEYWORDS = ("画", "绘", "图", "plot", "chart", "figure")
MODIFY_KEYWORDS = ("改", "调整", "换成", "变成", "加粗", "变大", "变小", "modify", "change")
ANALYSIS_KEYWORDS = ("拟合", "回归", "分析", "统计", "峰", "均值", "残差", "fit", "regression")
EXPORT_KEYWORDS = ("导出", "保存", "生成", "export", "save")

COLOR_WORDS = {
    "红": "red",
    "红色": "red",
    "蓝": "blue",
    "蓝色": "blue",
    "绿": "green",
    "绿色": "green",
    "黑": "black",
    "黑色": "black",
    "灰": "gray",
    "灰色": "gray",
}

OUTPUT_WORDS = {
    "png": "png",
    "svg": "svg",
    "pdf": "pdf",
    "opju": "opju",
    "origin": "opju",
}

MATERIAL_PLOT_KEYWORDS = (
    "xrd",
    "raman",
    "ftir",
    "xps",
    "xrf",
    "dsc",
    "tga",
    "eis",
    "nyquist",
    "cv",
    "lsv",
    "拉曼",
    "红外",
    "衍射",
    "光谱",
    "谱图",
    "图谱",
    "热重",
    "差示扫描",
    "阻抗",
    "应力应变",
    "充放电",
)

MATERIAL_LINE_KEYWORDS = (
    "xrd",
    "raman",
    "ftir",
    "xps",
    "xrf",
    "dsc",
    "tga",
    "cv",
    "lsv",
    "spectrum",
    "spectra",
    "拉曼",
    "红外",
    "衍射",
    "光谱",
    "谱图",
    "图谱",
    "热重",
    "差示扫描",
    "应力应变",
    "充放电",
)

MATERIAL_SCATTER_KEYWORDS = ("eis", "nyquist", "阻抗")


def infer_requirement(raw_text: str, profile: DatasetProfile | None = None) -> RequirementIntent:
    text = raw_text.strip()
    normalized = text.lower()
    assumptions: list[str] = []
    questions: list[ClarifyingQuestion] = []

    kind = _infer_kind(text, normalized)
    plot_kind = _infer_plot_kind(text, normalized)
    task_type = _infer_task_type(text, normalized, kind)
    style = _infer_style(text, normalized)
    output_formats = _infer_outputs(normalized)

    x_column: str | None = None
    y_column: str | None = None
    confidence = 0.45

    if kind != IntentKind.UNKNOWN:
        confidence += 0.2
    if plot_kind != PlotKind.AUTO:
        confidence += 0.1
    if output_formats:
        confidence += 0.05
    if style:
        confidence += 0.05

    if profile is None:
        questions.append(
            ClarifyingQuestion(
                field="dataset",
                question="请先上传或选择要处理的数据文件。",
            )
        )
    else:
        x_column, y_column, column_questions, column_assumptions = _infer_columns(text, profile, plot_kind)
        questions.extend(column_questions)
        assumptions.extend(column_assumptions)
        if x_column and y_column:
            confidence += 0.15

    if kind == IntentKind.UNKNOWN:
        questions.append(
            ClarifyingQuestion(
                field="intent",
                question="你想先画图、修改已有图，还是做拟合/统计分析？",
                options=("画图", "修改图", "拟合/统计"),
            )
        )
    elif plot_kind == PlotKind.AUTO and kind in {IntentKind.CREATE_PLOT, IntentKind.MODIFY_PLOT}:
        questions.append(
            ClarifyingQuestion(
                field="plot_kind",
                question="你希望输出哪种图？",
                options=("散点图", "折线图", "柱状图"),
            )
        )

    return RequirementIntent(
        raw_text=text,
        kind=kind,
        confidence=min(confidence, 0.95),
        task_type=task_type,
        plot_kind=plot_kind,
        x_column=x_column,
        y_column=y_column,
        group_column=_infer_group_column(text, profile),
        style=style,
        output_formats=output_formats,
        assumptions=tuple(assumptions),
        clarifying_questions=tuple(questions),
    )


def _infer_group_column(text: str, profile: DatasetProfile | None) -> str | None:
    if profile is None:
        return None
    if not any(keyword in text for keyword in ("分组", "按组", "按", "颜色", "多条", "group", "color")):
        return None
    numeric = set(profile.numeric_columns())
    for column in profile.columns:
        if column.name in numeric or column.name not in text:
            continue
        if f"按 {column.name}" in text or f"按{column.name}" in text or f"{column.name} 分组" in text:
            return column.name
    for column in profile.columns:
        if column.name in text and column.name not in numeric:
            return column.name
    return None


def _infer_kind(text: str, normalized: str) -> IntentKind:
    if any(word in text or word in normalized for word in MODIFY_KEYWORDS):
        return IntentKind.MODIFY_PLOT
    if any(word in text or word in normalized for word in PLOT_KEYWORDS):
        return IntentKind.CREATE_PLOT
    if any(word in text or word in normalized for word in MATERIAL_PLOT_KEYWORDS):
        return IntentKind.CREATE_PLOT
    if any(word in text or word in normalized for word in ANALYSIS_KEYWORDS):
        return IntentKind.ANALYZE
    if any(word in text or word in normalized for word in EXPORT_KEYWORDS):
        return IntentKind.EXPORT
    return IntentKind.UNKNOWN


def _infer_plot_kind(text: str, normalized: str) -> PlotKind:
    if "散点" in text or "scatter" in normalized:
        return PlotKind.SCATTER
    if "折线" in text or "曲线" in text or "line" in normalized:
        return PlotKind.LINE
    if "柱状" in text or "柱形" in text or "bar" in normalized:
        return PlotKind.BAR
    if "直方" in text or "hist" in normalized:
        return PlotKind.HISTOGRAM
    if any(word in text or word in normalized for word in MATERIAL_SCATTER_KEYWORDS):
        return PlotKind.SCATTER
    if any(word in text or word in normalized for word in MATERIAL_LINE_KEYWORDS):
        return PlotKind.LINE
    return PlotKind.AUTO


def _infer_task_type(text: str, normalized: str, kind: IntentKind) -> TaskType:
    if any(word in text or word in normalized for word in ANALYSIS_KEYWORDS):
        return TaskType.PLOT_XY if kind in {IntentKind.CREATE_PLOT, IntentKind.MODIFY_PLOT} else TaskType.REGRESSION
    if kind in {IntentKind.CREATE_PLOT, IntentKind.MODIFY_PLOT}:
        return TaskType.PLOT_XY
    return TaskType.DESCRIBE


def _infer_style(text: str, normalized: str) -> dict[str, str]:
    style: dict[str, str] = {}
    for word, color in COLOR_WORDS.items():
        if word in text or word in normalized:
            style["color"] = color
            break
    if "点" in text or "marker" in normalized:
        style["mark"] = "point"
    if "线条" in text or "连线" in text or "折线" in text or "line" in normalized:
        style["mark"] = "line"
    if "加粗" in text or "bold" in normalized:
        style["weight"] = "bold"
    return style


def _infer_outputs(normalized: str) -> tuple[str, ...]:
    outputs = []
    for word, output in OUTPUT_WORDS.items():
        if word in normalized and output not in outputs:
            outputs.append(output)
    return tuple(outputs)


def _infer_columns(
    text: str,
    profile: DatasetProfile,
    plot_kind: PlotKind = PlotKind.AUTO,
) -> tuple[str | None, str | None, list[ClarifyingQuestion], list[str]]:
    all_columns = [column.name for column in profile.columns]
    numeric_columns = profile.numeric_columns()
    questions: list[ClarifyingQuestion] = []
    assumptions: list[str] = []

    mentioned_all = [column for column in all_columns if column in text]
    mentioned_numeric = [column for column in numeric_columns if column in text]

    if plot_kind == PlotKind.HISTOGRAM:
        if mentioned_numeric:
            return None, mentioned_numeric[0], questions, assumptions
        if len(numeric_columns) == 1:
            assumptions.append(f"使用唯一数值列作为直方图变量：{numeric_columns[0]}。")
            return None, numeric_columns[0], questions, assumptions
        questions.append(
            ClarifyingQuestion(
                field="histogram_column",
                question="检测到多个数值列，请确认直方图要统计哪一列。",
                options=tuple(numeric_columns),
            )
        )
        return None, None, questions, assumptions

    if plot_kind == PlotKind.BAR:
        group_column = _infer_group_column(text, profile)
        visible_columns = [column for column in mentioned_all if column != group_column]
        if len(visible_columns) >= 2:
            return visible_columns[0], visible_columns[1], questions, assumptions
        if len(all_columns) == 2 and len(numeric_columns) == 1:
            x_column = next(column for column in all_columns if column not in numeric_columns)
            y_column = numeric_columns[0]
            assumptions.append(f"使用分类列 {x_column} 作为横轴，数值列 {y_column} 作为纵轴。")
            return x_column, y_column, questions, assumptions
        questions.append(
            ClarifyingQuestion(
                field="columns",
                question="柱状图需要确认分类列和数值列。",
                options=tuple(all_columns),
            )
        )
        return None, None, questions, assumptions

    mentioned = mentioned_numeric
    if len(mentioned) >= 2:
        return mentioned[0], mentioned[1], questions, assumptions

    if not mentioned and ("横轴" in text or "纵轴" in text or "x 轴" in text or "y 轴" in text):
        questions.extend(
            (
                ClarifyingQuestion(
                    field="x_column",
                    question="没有在数据中找到你指定的横轴列，请从可用数值列中选择。",
                    options=tuple(numeric_columns),
                ),
                ClarifyingQuestion(
                    field="y_column",
                    question="没有在数据中找到你指定的纵轴列，请从可用数值列中选择。",
                    options=tuple(numeric_columns),
                ),
            )
        )
        return None, None, questions, assumptions

    if len(numeric_columns) == 2:
        assumptions.append(f"使用前两个数值列作为 X/Y：{numeric_columns[0]} -> {numeric_columns[1]}。")
        return numeric_columns[0], numeric_columns[1], questions, assumptions

    if len(numeric_columns) > 2:
        questions.extend(
            (
                ClarifyingQuestion(
                    field="x_column",
                    question="检测到多个数值列，请确认横轴。",
                    options=tuple(numeric_columns),
                ),
                ClarifyingQuestion(
                    field="y_column",
                    question="检测到多个数值列，请确认纵轴。",
                    options=tuple(numeric_columns),
                ),
            )
        )
        return None, None, questions, assumptions

    questions.append(
        ClarifyingQuestion(
            field="columns",
            question="没有检测到足够的数值列，至少需要两个数值列才能画 XY 图。",
        )
    )
    return None, None, questions, assumptions
