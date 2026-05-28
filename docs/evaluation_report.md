# 需求理解评测报告

## 评测目标

评估当前系统能否把用户的自然语言画图需求收束成可执行槽位，包括意图、图类型、横纵轴、分组列、样式、输出格式、是否需要追问、最终是否可执行。

## 用例来源

基础 16 个用例参考了常见在线可视化示例族、NL2VIS/Text2Vis 基准和科研场景：

- [Vega-Lite 示例库](https://vega.github.io/vega-lite/examples/)：simple bar、grouped bar、histogram、scatter、multi-series line、regression 等图形家族。
- [nvBench / NL2VIS](https://github.com/TsinghuaDatabaseGroup/nvBench)：提供跨领域自然语言到可视化的 chart、x/y、classify 等标注结构。
- [nvBench 2.0](https://github.com/HKUSTDial/nvBench-2.0)：强调自然语言可视化中的歧义查询和多种有效解释。
- [Text2Vis](https://github.com/vis-nlp/Text2Vis) / [VisEval](https://github.com/microsoft/VisEval)：强调从自然语言生成准确、合法、可读的可视化，并提示后续要做可执行性、匹配度、可读性等多维评价。
- 科研 XY 曲线场景：电化学/传感器类 voltage-current、time-signal 曲线。

材料领域新增 8 个用例，关注仪器导出文件到图表的第一步转换：

- XRD：参考 [pymatgen diffraction 文档](https://pymatgen.org/pymatgen.analysis.diffraction.html) 中 `DiffractionPattern` 的 `x = two theta`、`y = intensity` 结构，以及 [RRUFF 下载页](https://www.rruff.net/about/download-data/) 的 powder XRD `.txt` 数据。
- Raman：参考 [RRUFF 下载页](https://www.rruff.net/about/download-data/) 中 Raman spectra `.txt` 数据形态。
- TGA/DSC：参考 [TA Instruments TRIOS](https://www.tainstruments.com/trios-software/) 对 Text/CSV/Excel/JSON 的导出能力。
- 电池循环：参考 [NASA Li-ion Battery Aging Datasets](https://data.nasa.gov/dataset/li-ion-battery-aging-datasets) 的 charge/discharge/EIS 循环数据说明。
- EIS/Nyquist：参考 [impedance.py plotting example](https://impedancepy.readthedocs.io/en/latest/examples/plotting_example.html) 的 `frequencies, Z = readCSV(...)` 工作流，以及 [PyBaMM EIS 示例](https://docs.pybamm.org/en/v26.4.0/source/examples/notebooks/simulations_and_experiments/eis-simulation.html) 对 Nyquist 图使用 `Re(Z)` 和 `-Im(Z)` 的说明。
- 应力应变：参考 [Instron Bluehill Universal](https://www.instron.com/en/products/materials-testing-software/bluehill-universal/) 和 [raw data export options](https://www.instron.com/en/resources/literature/bluehill-universal-results-and-raw-data-exports/) 中原始数据/CSV/自定义文本导出能力。

具体用例在 `examples/eval_cases.json`。

## 当前结果

2026-05-28 当前本机基线：

- `python -m unittest discover -s tests`：21 个测试通过。
- `python scripts\evaluate_intake_cases.py --planner rule`：24 个用例，字段准确率 100%，可用率 100%。
- `python scripts\evaluate_route_cases.py --planner rule`：8 个用例，字段准确率 100%，可用率 100%。
- `python scripts\evaluate_modify_cases.py --planner rule`：8 个用例，字段准确率 100%，可用率 100%。
- `python scripts\qwen_smoke_test.py --model qwen3.7-max`：通过，key 来源为本地安全存储。
- `scripts\origin_smoke_test.py`：真实 Origin smoke 通过，生成 OPJU、PNG、Origin render metadata、plot accuracy 和 visual quality artifact。
- MVP 验收门槛集中维护在 `docs/mvp_acceptance.md`。

规则版 baseline：

```powershell
python scripts\evaluate_intake_cases.py --planner rule --out runs\evals\intake_eval_rule_materials.json
```

结果：

- 用例数：24
- 字段准确率：100%
- 可用率：100%
- 覆盖新增材料场景：XRD、Raman、TGA、DSC、电池充放电、EIS Nyquist、应力应变、粒径分布。

千问 `qwen3.7-max`：

```powershell
python scripts\evaluate_intake_cases.py --planner qwen --out runs\evals\intake_eval_qwen_materials.json
```

结果：

- 用例数：24
- 字段准确率：100%
- 可用率：100%
- 覆盖：散点拟合、折线图、柱状图、分组柱状图、直方图、英文请求、样式颜色、PDF/OPJU 导出、多序列分组、无效列追问、多数值列追问，以及材料领域新增 8 类用例。

## 已覆盖能力

- 散点图 + 线性拟合 + PNG。
- 折线图 + SVG。
- 分类-数值柱状图。
- 分组柱状图。
- 单数值列直方图。
- 两个数值列时自动默认 X/Y。
- 多个数值列时追问 X/Y。
- 无效列名时追问。
- 英文自然语言请求。
- 蓝色样式和多格式导出。
- 按组上色和多条曲线。
- 带仪器元数据前缀的 CSV/TSV/TXT 文件：自动跳过 `#` 注释、`[Data]` 段名和常见元数据行。
- 逗号、分号、Tab、空格分隔的表格数据。
- 材料领域谱线/曲线默认图型：XRD/Raman/TGA/DSC/电池/应力应变默认 line；EIS/Nyquist 默认 scatter。

## 尚未覆盖

- 真实论文图审美评分。
- Origin 导出图与参考图的像素级对比。
- 误差棒、双坐标轴、箱线图、热图、峰分析、Tafel/CV、XPS 分峰、XRD 峰匹配/物相检索等学科模板。
- 仪器专有二进制格式、Excel 多工作表、多段重复扫描、单位行/注释行更复杂的导入形态。
- 用户连续修改图的多轮对话目前已列入 MVP 验收门槛，但还需要连续两轮以上的自动评测用例。
- 输出图是否“好看”的审美评估尚未覆盖；当前只验收确定性视觉健康检查和 Origin metadata 对齐。

## 下一步评估

1. 加图像级评估：把 Origin 导出图和参考图 spec 对齐，检查图类型、轴、图例、拟合线、分组颜色。
2. 加多轮修改评估：从“画图”到“改颜色/改线宽/调图例/导出”的连续会话。
3. 加科研模板评估：CV、LSV、标准曲线、峰面积、误差棒和多组重复实验。
