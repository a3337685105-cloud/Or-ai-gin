# Ready-To-Copy Prompts

Use one prompt per new Codex conversation. Start each conversation in the matching branch or
worktree folder.

## 0. Core Baseline

Branch: `codex/research-assistant-core`

```text
请在 codex/research-assistant-core 分支工作。

目标：把当前科研助手/热仿真基础整理成可并行开发的稳定基线。

背景：
- 产品必须是单入口科研助手，不要暴露 COMSOL/Origin/V&V/报告等多个模式。
- 主线是：用户目标和文件 -> 厚输入 intake -> 薄 ResearchWorkOrder -> 仿真/分析 -> 图像动图/报告/V&V 证据包。
- 当前已有 research intake、COMSOL discovery/batch runner、thermal harness、相关设计文档。

任务：
1. 检查当前 README、docs、src、tests 的一致性。
2. 确认 `python -m unittest discover -s tests` 通过。
3. 梳理当前新增文件，补齐缺失的 README 链接和开发命令。
4. 不做大功能，只做基线整理、命名统一和明显缺口修复。

验收：
- 测试通过。
- README 指向关键文档。
- 当前基础能力可以作为其他分支的 base。
- 不要改动与任务无关的文件，不要删除用户未提交文件。
```

## 1. Unified Research Intake

Branch: `codex/unified-research-intake`

```text
请在 codex/unified-research-intake 分支工作。

目标：完善单入口科研助手 intake，把用户自然语言和可选文件压缩成 ResearchWorkOrder。

必须保持一个用户入口：
用户提供“目标 + 可选文件 + 期望输出”，系统内部再判断需要仿真、画图、报告还是验证。

重点实现：
1. 完善 `src/origin_ai_lab/agents/research_intake_harness.py`。
2. 把 thick_context / core_thread / assumptions / missing_blockers / next_questions 做得更稳定。
3. 增加 EvidenceTrace 的初始结构，记录信息来自用户、文件、默认值、文献还是工具输出。
4. 根据用户用途区分：自己判断、实验方案、展示、论文插图、验证报告。
5. 前端或 API 层只暴露一个 intake 入口，不要新增多个模式入口。

测试：
- 增加中文科研需求样例测试。
- 覆盖“信息很少需要追问”和“信息足够可规划”的情况。
- 运行 `python -m unittest discover -s tests`。

交付：
- 代码变更路径、测试结果、剩余风险。
```

## 2. COMSOL Result Export

Branch: `codex/comsol-result-export`

```text
请在 codex/comsol-result-export 分支工作。

目标：让 COMSOL backend 不只是运行 `.mph`，还要导出有用结果。

背景：
- 当前 `ComsolThermalClient` 已能通过 `comsolbatch` 跑官方 `busbar_smoke`。
- 下一步是从 solved model 或 COMSOL batch/report 能力中导出图像、CSV、max temperature、日志摘要。

重点实现：
1. 扩展 `src/origin_ai_lab/connectors/comsol_client.py`。
2. 探索 COMSOL command line / method call / report/export 的最小可靠路径。
3. 输出至少：
   - solved `.mph`
   - batch log
   - result manifest
   - 若可行，温度场 PNG 或 COMSOL report
   - 若可行，max temperature 或导出的 table CSV
4. 不要让 LLM 直接执行任意 COMSOL 脚本；只接入受控模板/方法。

测试：
- 继续保证无 COMSOL 时 mock/dry-run 不坏。
- 有 COMSOL 时可跑 `--case busbar_smoke`。
- 运行 `python -m unittest discover -s tests`。

交付：
- 说明哪些导出已真实跑通，哪些仍需 COMSOL API/method 支持。
```

## 3. Thermal Visual Package

Branch: `codex/thermal-visual-package`

```text
请在 codex/thermal-visual-package 分支工作。

目标：实现热仿真可视化证据包，不只是单张温度图。

产品原则：
- 用户仍然只有一个入口。
- 视觉输出是 ResearchWorkOrder 的结果，不是独立模式。
- Origin 主要负责 1D/2D 曲线、参数扫描、实验对比。
- 3D 温度场、切片、流线、动画优先用 COMSOL 导出或 Python/PyVista/ParaView 路径。

重点实现：
1. 设计 `thermal_visualization_spec` / `VisualizationSpec`。
2. 定义默认图包：
   - temperature overview
   - key slice
   - isotherm / threshold view
   - heat flux view
   - probe/path curves
   - parameter comparison
   - animation manifest
3. 加入质量规则：单位、色标、时间/参数标签、帧完整性、非空图像。
4. 先可以生成 manifest 和占位检查，再逐步接真实导出。

测试：
- manifest 生成测试。
- 图像/动画质量检查的纯函数测试。
- `python -m unittest discover -s tests`。
```

## 4. Simulation Report Builder

Branch: `codex/simulation-report-builder`

```text
请在 codex/simulation-report-builder 分支工作。

目标：生成科研人员能直接看的仿真报告，而不是散落的 JSON 和图片。

输入：
- ResearchWorkOrder
- thermal_simulation_result
- visualization manifest
- COMSOL/Origin artifacts
- validation checks

输出：
- `thermal_report_manifest.json`
- Markdown 或 HTML 报告
- artifact index
- evidence gap list

报告至少包含：
1. 摘要和结论边界
2. 用户目标和判据
3. 输入、假设、材料、热源、边界条件
4. 模型/求解器/软件版本
5. 结果图和数值表
6. 验证状态和风险
7. 文件/日志/可复现索引

注意：
- 报告要明确标注缺失证据，不能假装完整。
- 区分内部判断版、展示版、论文/外部声明版。

测试：
- 用 mock thermal result 生成报告。
- 检查 manifest 完整性。
- `python -m unittest discover -s tests`。
```

## 5. Thermal V&V Harness

Branch: `codex/thermal-vv-harness`

```text
请在 codex/thermal-vv-harness 分支工作。

目标：让热仿真结果经得起检验。

重点实现：
1. 扩展官方 COMSOL golden case registry。
2. 增加求解日志解析：完成状态、警告、运行时间、残差/迭代信息（能取多少取多少）。
3. 定义 boundary-condition audit 数据结构。
4. 定义 energy-balance check 数据结构。
5. 设计 mesh/time-step convergence runner 接口，不一定第一版全自动跑。
6. 输出 credibility card：输入完整度、验证状态、风险和缺口。

测试：
- 不依赖 COMSOL 的解析/结构测试。
- 如本机有 COMSOL，可跑 `busbar_smoke`。
- `python -m unittest discover -s tests`。

原则：
- V&V 是内部能力，不是前端独立入口。
- 当用户要论文/对外结论时，系统自动提高证据要求。
```

## 6. Research Assistant Workbench

Branch: `codex/research-assistant-workbench`

```text
请在 codex/research-assistant-workbench 分支工作。

目标：把前端改成单入口科研助手工作台。

产品原则：
- 不要暴露 COMSOL模式、Origin模式、报告模式、验证模式。
- 只暴露一个研究目标输入框和上下文/文件区。

建议界面：
- 顶部：研究目标输入框
- 左/中：上下文和结果摘要
- 右：AI 理解卡，可编辑核心槽位
- 结果 tabs：Summary / Model / Results / Figures / Validation / Files

重点实现：
1. 前端调用 `research-intake` 或后端等价 API。
2. 显示 thick-to-thin 结果：
   - 用户目标
   - 系统理解
   - 假设
   - 缺失信息
   - 下一步计划
3. 不要堆专家表单，只展示当前任务最相关字段。
4. 保留后续接仿真/图像/报告结果的区域。

测试：
- 如有 web UI 测试，跑现有测试。
- 手动启动 web server 检查页面。
- `python -m unittest discover -s tests`。
```

