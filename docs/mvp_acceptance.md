# MVP 验收门槛

本文档定义当前 Origin AI Lab MVP 的最低验收标准。目标不是证明系统已经覆盖所有科研绘图任务，而是保证每次交付都有可复现的基线、明确的失败条件和可审计的 artifact。

## Gate 0：仓库与环境基线

- 仓库包含可运行的 `pyproject.toml`、CLI、Web UI、测试、示例数据和项目说明。
- `python -m pip install -e .` 可以成功安装开发包。
- 如果 Windows 用户 Scripts 目录不在 `PATH`，验证命令应使用 `python -m origin_ai_lab.cli` 作为稳定入口。
- `runs/`、私有数据、Origin 项目导出、缓存和密钥不得进入提交。

## Gate 1：离线确定性闭环

必须通过：

```powershell
python -m unittest discover -s tests
python scripts\evaluate_intake_cases.py --planner rule
python scripts\evaluate_route_cases.py --planner rule
python scripts\evaluate_modify_cases.py --planner rule
python scripts\check_guardrails.py --policy .codex\harness-policy.json
python -m origin_ai_lab.cli analyze examples\sample_xy.csv --out runs\status_check --no-origin
```

验收条件：

- 单元测试全部通过，允许测试中显式标注的跳过项。
- intake、route、modify 评估的字段准确率和可用率不得回退。
- 离线分析必须生成 `plan.json`、`plot_spec.json`、`plot_accuracy.json`、`result.json`。
- `result.json` 中 error 级别检查不得失败。

## Gate 2：Qwen Planner Smoke

必须通过：

```powershell
python scripts\qwen_smoke_test.py --model qwen3.7-max
```

验收条件：

- API key 只能来自环境变量或本地安全存储，不能写入仓库。
- Qwen 输出必须被解析成结构化 intent。
- 如果 Qwen 不可用，系统必须能回退到规则 planner，且发布说明中记录 Qwen 未验证。

## Gate 3：真实 Origin Smoke

必须在装有 Origin/OriginPro 许可证的 Windows 本机通过：

```powershell
& "C:\Users\hp\Documents\New project\cad-origin-env\Scripts\python.exe" scripts\origin_smoke_test.py
```

验收条件：

- 生成 OPJU 项目和至少一个 PNG 图像。
- `origin_render_metadata.json`、`visual_quality.json`、`plot_accuracy.json` 必须生成。
- Origin 轴标题、拟合线状态、导出格式必须与 `PlotSpec` 一致。
- Origin/COM 失败必须被记录为外部软件不可用，而不是被误判为科学结果失败。

## Gate 4：多轮图表修改

多轮修改是 MVP 的正式验收项，不再只是后续增强。

最低验收场景：

1. 从一个已完成 run 继续修改，例如“把点改成红色”。
2. 在上一版基础上再修改，例如“去掉拟合线”或“横坐标从 0 到 10”。
3. 每一轮都生成新的 revision 目录，保留上一版 artifact。
4. 每一轮都保存 `edit_plan.json`、新版 `plot_spec.json` 和新版 `result.json`。
5. 修改计划只能使用白名单操作，不能让 AI 直接执行 Origin/LabTalk。
6. 模糊请求，例如“让它更像论文图”，必须追问或选择明确模板，不能静默改图。

验收命令：

```powershell
python scripts\evaluate_modify_cases.py --planner rule
```

后续需要补充连续两轮以上的自动评测用例：初始作图、改颜色、改坐标/拟合、导出新版，并验证 revision 链可重放。

## Gate 5：视觉质量

视觉质量是 MVP 的正式验收项，但只作为确定性图像健康检查和结构对齐检查，不作为科学结论。

最低验收项：

- `visual_image_exists`：图像文件存在。
- `visual_dimensions`：分辨率达到最低目标。
- `visual_nonblank`：图像不是空白。
- `visual_content_visible`：有效内容区域足够。
- `visual_contrast`：线条和文本具备基本可见对比度。
- `visual_not_clipped`：内容没有严重贴边裁切。
- `plot_axis_titles_declared`：spec 中声明轴标题。
- `origin_axis_titles_match`：Origin 渲染元数据中的轴标题与 spec 一致。
- `origin_fit_line_rendered`：拟合线状态与 spec 一致。
- `origin_export_formats`：请求的导出格式全部生成。

验收条件：

- error 级视觉/准确性检查失败时，本轮不算通过。
- warning 级检查可以不阻塞，但必须进入 `result.json`。
- 视觉模型或审美评分只能作为建议或 warning，不能覆盖确定性校验。

## Gate 6：交付记录

每次准备提交或发布前，必须记录：

- 跑过哪些命令。
- Qwen 和 Origin 是否实际验证。
- 哪些风险仍未覆盖。
- 是否新增或更新了评估用例、示例数据或设计文档。

当前基线日期：2026-05-28。
