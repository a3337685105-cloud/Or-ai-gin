# 图像修改能力设计

## 目标

生成第一张图之后，用户可以继续用自然语言要求修改，例如：

- “把散点改成蓝色，拟合线加粗一点。”
- “横坐标从 0 到 10，纵坐标标题改成 Current / mA。”
- “不要拟合线，只保留散点。”
- “按 treatment 分组上色，图例放右上角。”
- “改成 8 cm 宽，导出 600 dpi 的 png 和 origin 项目。”

修改功能的关键不是让 AI 直接碰图，而是把自然语言修改收束成可验证、可回滚、可重放的编辑操作。

## 修改请求分类

第一阶段应覆盖这些高频修改：

1. 数据映射：切换 x/y 列、增加分组列、切换图类型。
2. 分析层：添加/删除线性拟合、切换拟合模型、添加误差棒、归一化、过滤数据。
3. 样式层：颜色、点型、线型、线宽、字体、字号、坐标轴标题、图标题。
4. 坐标层：坐标范围、刻度间隔、对数坐标、反向坐标、网格线。
5. 图例/标注：图例位置、系列名称、文本标注、箭头、显著性标记。
6. 版式/导出：图尺寸、DPI、边距、输出格式、Origin 项目保存。

第一阶段不要把所有 Origin 细节暴露给用户。前端只需要一个“继续修改”输入框、可见的当前图状态、几个常用快捷按钮和版本历史。

## 方案 A：Spec-first 重生成

系统把图的真实状态保存成一个规范化 `PlotSpec`，用户每次修改都生成 `PlotEditPlan`，先修改 spec，再从原始数据重新生成图。

推荐作为 MVP 主路线。

### 数据结构草案

```json
{
  "schema_version": "plot-spec/v1",
  "dataset_path": "examples/sample_xy.csv",
  "plot": {
    "kind": "scatter",
    "x": "time_s",
    "y": "signal_v",
    "group": null,
    "fit": {"enabled": true, "model": "linear"}
  },
  "style": {
    "series": [{"target": "signal_v", "color": "#1f77b4", "marker": "circle"}],
    "fit_line": {"color": "#b45f06", "width": 2},
    "axes": {
      "x": {"title": "time_s", "limits": null},
      "y": {"title": "signal_v", "limits": null}
    },
    "legend": {"visible": true, "position": "top_right"},
    "export": {"formats": ["png"], "width_px": 1400}
  }
}
```

```json
{
  "schema_version": "plot-edit-plan/v1",
  "base_run_id": "2026-05-27-001",
  "user_request": "把点改成红色，拟合线加粗",
  "operations": [
    {"op": "set_series_style", "target": "signal_v", "properties": {"color": "red"}},
    {"op": "set_fit_style", "properties": {"width": 3}}
  ],
  "requires_confirmation": false,
  "assumptions": []
}
```

### 优点

- 可测试：不启动 Origin 也能测试“自然语言 -> edit plan -> spec diff”。
- 可回滚：每次修改保存成 revision。
- 可复现：从原始数据和 revision 链可以重建最终图。
- 可验证：所有编辑操作先过 schema、列名、数值范围、格式白名单。
- 可迁移：同一 spec 以后可以输出到 Origin、Matplotlib、Plotly、SVG。

### 缺点

- 不能完整保留用户在 Origin 里手动做的所有细节。
- Origin 高级图形属性需要逐步纳入 spec，否则会丢失。

### 适合场景

用户主要通过本软件生成和修改图；我们希望科学结果可追溯。

## 方案 B：直接修改 Origin 项目

系统打开上一版 `.opju`，找到图页、图层、数据 plot，然后通过 `originpro` 和 LabTalk 修改当前 Origin 对象。

Origin 官方能力支持这个方向：`originpro.project.open/save` 可打开/保存项目；`GPage.save_fig` 可导出图；`GLayer.set_xlim/set_ylim` 可改坐标范围；`Plot.set_cmd()` 可执行 LabTalk `set` 命令修改 plot 属性；LabTalk `set` 命令本身用于修改 dataset、data plot、worksheet 属性。

### 可执行路径

1. 打开上一版项目：`op.open(project_path)`。
2. 定位目标图：优先用 artifact metadata 里的 graph name；否则使用 `op.find_graph(0)`。
3. 定位图层和曲线：`graph[0]`、`layer.plot_list()`。
4. 应用修改：
   - 坐标范围：`layer.set_xlim(begin, end, step)` / `layer.set_ylim(...)`
   - 曲线样式：`plot.set_cmd("-c 2", "-w 1000")`
   - 重新缩放：`layer.rescale()`
   - 图例：使用 LabTalk `legend` 命令或模板逻辑。
5. 导出新版图片并另存新版 OPJU。

### 优点

- 能保留 Origin 项目内部状态，适合接着用户已有项目改。
- 对简单样式修改很快，不必完整重建。
- 可以逐步调用 Origin 高级功能、模板和 LabTalk。

### 缺点

- 对象定位脆弱：图名、图层、plot 顺序可能变化。
- 属性命令需要维护 Origin/LabTalk 映射表。
- 难做跨版本验证和回滚。
- 自动修改真实项目风险高，必须另存副本并记录变更。

### 适合场景

用户上传或指定已有 Origin 项目；需求是“把这个现成图改一下”。

## 方案 C：混合方案

以 `PlotSpec` 为源头真相，同时保留 Origin 项目作为可编辑 artifact。默认修改走 spec 重生成；遇到 Origin 特有能力或用户明确要求“在这个 Origin 项目上继续改”，才走直接修改项目。

推荐作为产品长期路线。

### 决策规则

- 数据映射、拟合、输出格式、颜色、字体、轴标题、图例位置：优先改 spec 并重生成。
- Origin 模板、复杂多图层、已有 OPJU 手工图、特殊 LabTalk 属性：走 Origin direct edit，但必须另存 revision。
- 修改请求含糊，比如“好看一点”“论文风格”：先给 2-3 个候选方向或应用预设模板，不直接执行不可解释操作。

## 方案 D：模板/主题驱动

把常用论文图风格、学科图模板、实验室模板做成 `TemplateSpec` 或 Origin 模板。AI 修改请求不是微调每个属性，而是选择模板加少量覆盖项。

### 优点

- 更容易做出好看的图。
- 适合重复科研工作流，例如 CV、LSV、Tafel、标准曲线、XRD、Raman。
- 可让 PI 或课题组沉淀统一风格。

### 缺点

- 需要前期模板库。
- 模板适配的数据结构必须严格定义。

### 推荐用法

作为第二阶段能力：先用少量通用模板，再做学科模板包。

## 方案 E：视觉反馈闭环

导出图像后，系统对照用户修改请求和目标 spec 做自动检查。

第一阶段可以做结构检查：

- 是否存在目标文件。
- 图类型、x/y/group/fitting 是否和 spec 一致。
- 输出格式和尺寸是否符合要求。
- 数值结果是否没有变化或变化符合预期。

第二阶段再加图像检查：

- 用 SVG/图像解析检查轴标题、图例、颜色、线宽的大致存在性。
- 用视觉模型对“是否像参考图”“图例是否挡住曲线”“文字是否重叠”打分。

视觉评估只做辅助，不作为科学结论。

## 推荐落地路线

### MVP：两周内可做的版本

1. 扩展 `plot_spec.json`，把当前图的图类型、x/y、group、fit、style、export 都保存进去。
2. 新增 `PlotEditPlan` 和编辑操作白名单。
3. 新增 `qwen_edit_planner.py`：输入用户修改请求、当前 spec、数据 profile，输出 edit plan。
4. 新增 `POST /api/modify`：参数为 `run_id`、`request`，返回 edit plan、spec diff、新版 artifacts。
5. 前端结果区增加“继续修改”输入框和 revision 列表。
6. 执行方式先采用 spec-first 重生成，Origin 项目每次另存到 `runs/<run_id>/revisions/<n>/`。
7. 增加 12 个修改评测用例：改颜色、改轴标题、改坐标范围、删除拟合、增加拟合、换图类型、增加分组、换导出格式、改图例、无效列名追问、模糊审美请求追问、连续两轮修改。

### 第二阶段

1. 加 Origin direct edit adapter，只支持一小组明确操作：轴范围、线宽、颜色、导出、图例重建。
2. 增加模板系统：论文默认模板、presentation 模板、灰度打印模板。
3. 对 Origin 导出图做结构级/图像级评估。
4. 支持用户导入已有 `.opju` 后修改。

## 后端模块建议

- `models.py`
  - `PlotSpec`
  - `PlotEditOperation`
  - `PlotEditPlan`
  - `PlotRevision`
- `agents/qwen_edit_planner.py`
  - 自然语言修改请求 -> 编辑操作。
- `plotting/spec_editor.py`
  - 纯函数：`apply_edit_plan(spec, plan) -> new_spec`。
- `plotting/spec_validator.py`
  - 校验列名、图类型、输出格式、坐标范围、样式白名单。
- `workflows/modify_plot.py`
  - 读取上一次 result/spec，应用修改，重跑分析和导出。
- `connectors/origin_client.py`
  - 后续增加 `open_project_copy()`、`apply_origin_edit_plan()`。

## 前端交互建议

- 图下方固定一个“继续修改”输入框。
- 显示当前图的关键信息：图类型、X、Y、分组、拟合、输出格式。
- 修改前展示 AI 理解到的变更摘要，例如“将散点颜色改为红色；拟合线宽改为 3”。
- 提供撤销/回到上一版。
- 对含糊请求给选项，而不是静默执行，例如“更像论文图”可以追问“黑白打印 / Nature 风格 / 更大字号”。

## 风险控制

- 永远不覆盖原始数据和上一版 OPJU。
- 所有修改写入 artifact log。
- 直接 Origin 修改必须另存副本。
- AI 只能产出 edit plan，不能绕过校验直接执行 LabTalk。
- 修改分析方法、拟合模型、筛选数据时必须在结果里显著记录。

## 结论

最稳的路线是：先做 `PlotSpec + EditPlan + Regenerate`，把修改功能做成可测试、可回滚、可复现的核心能力；再补 `Origin direct edit`，用于已有 Origin 项目和少数高价值 Origin 特性；最后加入模板和视觉评估，让“改到好看”从主观聊天变成可检查的流程。
