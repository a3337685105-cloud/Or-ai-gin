# AI + Origin 科研自动化可行性报告

> 日期：2026-05-25
> 结论：可行，但应该从“模板化科研助理”开始，而不是从“全自动科学家”开始。

## 调研团队结论

本次按 Hermes jury 的方式做本地团队模拟，拆成六个小组：科研用户需求组、Origin 自动化组、AI Agent 架构组、数据与统计验证组、安全合规组、产品商业化组。

综合 verdict：`RECOMMENDED_WITH_MODIFICATIONS`。

这个项目值得做。最先能落地的场景不是替研究者“判断科学发现”，而是把高频、重复、容易出错的基础工作自动化：导入数据、清洗列名和单位、批量拟合、套用 Origin 模板、导出图、生成方法记录和可复查报告。真正的护城河不是接一个大模型，而是把科研工作流拆成可验证的工具调用，把每一步输入、参数、输出和检查结果留下来。

## 需求判断

强需求存在，尤其在材料、化学、电化学、生物物理、传感器、谱学、动力学实验等领域。典型任务包括：

- 把仪器导出的 CSV/TXT/Excel 导入 Origin。
- 识别 X/Y/误差列、单位、样品组、重复实验。
- 做线性/非线性拟合、峰识别、基线扣除、平滑、归一化、统计检验。
- 按实验室固定格式画图，批量导出 PNG/SVG/PDF。
- 保存 OPJU 项目、分析参数、图表模板和报告。
- 对结果做 sanity check：样本量、缺失值、异常值、拟合残差、参数置信区间、图轴范围。

用户愿意为它付费的前提是：少点玄学，多点复现。科研用户不会长期信任一个只会“看起来画得不错”的 AI；他们需要知道每个参数从哪里来，为什么这样拟合，能不能一键复跑。

## 官方资料支撑

Origin 侧可行性很明确：

- OriginLab 官方文档说明，外部 Python 可通过 `originpro` 访问 Origin；`originpro` 是基于 Origin Automation Server COM 的高层 API，能读写/修改数据、创建和导出图，并会启动一个本地 Origin 实例；该路径是 Windows-only，且需要本机安装 Origin 2021 或更高版本。见 [OriginLab Python External docs](https://docs.originlab.com/externalpython)。
- 官方外部 Python 示例展示了推荐 wrapper：开发时让 Origin 可见，异常时关闭实例，结束时 `op.exit()`。见 [External Python Code Samples](https://www.originlab.com/doc/en/ExternalPython/External-Python-Code-Samples)。
- Origin 还可作为 COM Automation Server，被支持 COM 的客户端程序控制。见 [Origin Automation Server docs](https://docs.originlab.com/com/)。
- Origin 的 Analysis Template 和 Batch Processing 本来就适合重复分析。官方文档说明 Analysis Template 可保存数据结构、元数据、公式、分析操作和图表，并用于批处理；Batch Processing 可用模板处理多个文件或项目内数据。见 [Analysis Templates](https://www.originlab.com/doc/Origin-Help/Analysis-Templates) 与 [Batch Processing](https://www.originlab.com/doc/Origin-Help/Batch-Processing)。

AI 侧可行性也明确，但要走“工具调用 + 结构化输出 + 评价”的路线：

- OpenAI 的工具调用文档把模型接入外部函数描述为多步流程：模型请求工具，应用执行代码，再把工具结果回传模型。见 [Function calling](https://platform.openai.com/docs/guides/function-calling?api-mode=responses)。
- OpenAI 的工具文档支持自定义函数、远程 MCP、文件搜索、网页搜索等扩展方式。见 [Using tools](https://platform.openai.com/docs/guides/tools?api-mode=responses)。
- Structured Outputs 可让模型输出遵守 JSON Schema，适合生成分析计划、参数、图表规范。见 [Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs?api-mode=chat)。
- Agents SDK 有 tracing，可记录 LLM 生成、工具调用、handoff、guardrail 和自定义事件，适合做科研自动化审计。见 [Agents SDK Tracing](https://openai.github.io/openai-agents-python/tracing/)。
- Agent evals 和 trace grading 适合建立持续评价集。见 [Agent evals](https://platform.openai.com/docs/guides/agent-evals)。

## 可行性评分

| 维度 | 评分 | 判断 |
|---|---:|---|
| 用户需求 | 5/5 | 重复分析、批量绘图、格式统一是刚需。 |
| Origin 接口 | 4/5 | 官方 `originpro`/COM 足够支撑 MVP；限制是 Windows、本机许可、进程稳定性。 |
| AI 接入 | 4/5 | 工具调用和结构化输出成熟；难点是约束模型不要乱选分析方法。 |
| 结果评价 | 3/5 | 可做，但必须为每类分析建立 golden dataset 和方法级检查。 |
| 工程复杂度 | 3/5 | 本地 Windows worker + Python 后端可控；跨平台和多软件扩展会增加复杂度。 |
| 商业风险 | 3/5 | 实验室付费意愿存在，但必须解决隐私、可复现和学习成本。 |

## 最大风险

1. 科学正确性风险：AI 容易把“能跑”误认为“方法正确”。需要把方法选择和参数确认设计成显式步骤。
2. Origin 运行时风险：COM 自动化依赖本机软件、许可证、进程状态。需要 worker 隔离、超时、重启和可见调试模式。
3. 数据隐私风险：未发表数据不应默认上传云端。需要本地模式、脱敏摘要、用户确认和日志开关。
4. 评价成本风险：每新增一个学科 workflow，都要配测试数据、预期结果和图表 QA。
5. 产品边界风险：一开始做成“万能科研 AI”会失控；应先做 3-5 个高频模板。

## 推荐切入点

MVP 只做一个窄而完整的闭环：

CSV/TXT 导入 -> 数据概况 -> 线性/非线性拟合或基础统计 -> Origin 模板绘图 -> 导出图和 OPJU -> 生成包含参数、假设、检查项的报告。

首批 workflow 建议：

- XY 曲线 + 线性拟合 + R2/残差检查。
- 多样品批量散点/折线图 + 统一样式导出。
- 峰识别/峰面积/半峰宽，先用 Origin/OriginPro 内置能力或 SciPy 做基准。
- 电化学 CV/LSV/Tafel 的基础指标提取。
- 标准曲线/剂量响应曲线。

## Go/No-Go

Go，但要加两个限制：

- AI 只生成结构化计划，不直接无审计地操作 Origin。
- 每个 workflow 必须有可重复运行的测试集和验收指标。

## 本机接口验证

2026-05-25 已在当前电脑运行：

```powershell
& "C:\Users\hp\Documents\New project\cad-origin-env\Scripts\python.exe" scripts\origin_smoke_test.py
```

结果：通过。脚本成功启动 Origin，导入 `examples/sample_xy.csv`，完成线性回归检查，并生成：

- `runs/origin_smoke/origin_ai_analysis.opju`
- `runs/origin_smoke/origin_ai_analysis.png`
- `runs/origin_smoke/result.json`

这说明本机 Origin 接口路径不是纸面可行，而是已经可调用。
