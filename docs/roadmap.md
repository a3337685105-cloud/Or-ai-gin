# Roadmap

## Milestone 0: Origin 接口烟测

状态：已完成。

- `scripts/origin_smoke_test.py` 已在本机通过。
- 产物包括 `runs/origin_smoke/origin_ai_analysis.opju` 和 `runs/origin_smoke/origin_ai_analysis.png`。
- 说明本机 Origin/OriginPro、许可证、`originpro` 包和图导出路径可用。

## Milestone 1: 需求收束 MVP

状态：进行中。当前已有规则版 intake 和最小 Web UI。

- 自然语言需求解析成 intent、slots、assumptions、clarifying questions。
- 前端展示“AI 理解为”的可编辑卡片。
- 支持最小任务：散点图、折线图、线性拟合、PNG/OPJU 导出。
- 用户缺少数据或列选择时，只追问必要问题。

## Milestone 2: 非 AI 的完整绘图闭环

- CSV/TXT 导入。
- 列类型识别和数据质量概览。
- XY 线性拟合。
- JSON 报告和 plot spec。
- Origin scatter/line 图导出。
- 单元测试和示例数据。

## Milestone 3: 图表修改工作流

- 用户可说“把点改成红色”“线条加粗”“改成折线图”“图例放右上角”。
- 后端维护图状态模型。
- 变更计划只改必要部分，不重复分析数据。
- 保存每次修改的 plan diff。
- MVP 验收要求见 `docs/mvp_acceptance.md`：至少覆盖连续 revision、`edit_plan.json`、spec diff、模糊修改追问和可重放 artifact 链。

## Milestone 3.5: 视觉质量验收

状态：进入 MVP 验收门槛。

- Origin 导出 PNG 后必须生成 `visual_quality.json`。
- error 级图像健康检查失败时，本轮不算通过。
- warning 级检查必须记录到 `result.json`，但不直接代表科学结论失败。
- 视觉模型或审美评分只能作为建议，不能覆盖确定性检查。
- MVP 验收要求见 `docs/mvp_acceptance.md`。

## Milestone 4: 模板化科研任务

- 引入任务模板：线性拟合、批量曲线、峰分析、标准曲线、电化学曲线。
- 每个模板有参数 schema、golden dataset、验收指标。
- 支持 Origin Analysis Template 和实验室风格模板。

## Milestone 5: LLM Planner

- 用结构化输出生成 intent/plan。
- validator 检查工具白名单、参数范围、数据列、隐私策略。
- 引入 trace log、用户反馈和失败样本库。

## Milestone 6: 产品化

- Web/Desktop UI。
- run history、参数确认、图预览、报告生成。
- 多实验室配置：本地模型、云模型、禁用云上传。

## Milestone 7: 多软件扩展

- MATLAB、Excel、GraphPad Prism、ImageJ、Jupyter 等连接器评估。
- 统一 Tool Registry 和 Artifact Contract。
- MCP server 暴露能力给外部 Agent。
