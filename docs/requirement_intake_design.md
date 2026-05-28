# 需求收束设计

## 为什么这是核心

Origin 的问题不只是“步骤多”，而是用户很难把想要的视觉效果和分析动作映射到正确菜单。这个软件要补的不是又一个菜单系统，而是一个翻译层：把人的愿望翻译成 Origin 可以执行、用户可以检查的计划。

## 前端设计

第一版不要做复杂工作台。做一个“数据 + 一句话 + 理解卡片 + 预览”的闭环。

### 页面结构

1. 数据入口
   拖入 CSV/Excel/Origin 项目。系统立即显示列名、类型、行数、缺失值。

2. 需求输入
   一个命令栏，例如：“把 time 和 signal 画成散点图，加线性拟合，导出 png。”

3. 理解卡片
   展示结构化槽位：
   - 任务：画图/改图/分析/导出
   - 图类型：散点图/折线图/柱状图
   - 数据：X 列、Y 列、分组列、误差列
   - 分析：线性拟合、平滑、峰分析
   - 样式：颜色、点型、线宽、字体、图例
   - 输出：PNG/SVG/PDF/OPJU

4. 追问区
   只显示阻塞问题。例如多个数值列时问“横轴和纵轴选哪两列？”不要让用户先填长表。

5. 预览区
   显示当前图和变更差异。用户继续说“点太大了”“换成红色”“不要网格线”，系统追加变更计划。

### 交互状态

- Need data：没有数据，先让用户上传。
- Need clarification：有多个可能解释，只问一两个关键问题。
- Ready to run：计划完整，可以执行。
- Running：Origin worker 执行。
- Needs review：输出图已生成，用户可继续修改。

## 后端设计

### 核心对象

`RequirementIntent` 是后端第一入口。它把自然语言变成稳定字段：

- `raw_text`
- `kind`
- `confidence`
- `task_type`
- `plot_kind`
- `x_column`
- `y_column`
- `style`
- `output_formats`
- `assumptions`
- `clarifying_questions`

第一版用规则 parser，后续把同一个 schema 交给 LLM structured output。

### API 草案

```text
POST /datasets
POST /datasets/{id}/profile
POST /intents
POST /plans
POST /plans/{id}/validate
POST /runs
POST /runs/{id}/messages
GET  /runs/{id}
```

### 执行流程

1. Profile data。
2. Parse user request into intent。
3. Fill obvious slots。
4. Ask only blocking questions。
5. Build executable plan。
6. Validate plan。
7. Run Python/Origin tools。
8. Save artifacts and audit trail。
9. Let user revise by natural language。

## 当前代码落点

- `src/origin_ai_lab/agents/requirement_intake.py`：规则版需求解析。
- `src/origin_ai_lab/models.py`：`RequirementIntent`、`ClarifyingQuestion` 等数据结构。
- `origin-ai intake "..." --dataset examples/sample_xy.csv`：命令行验证入口。

示例：

```powershell
$env:PYTHONPATH='src'
python -m origin_ai_lab intake "帮我画散点图，加线性拟合，导出 png" --dataset examples\sample_xy.csv
```

输出会包含可执行槽位：`create_plot`、`scatter`、`time_s`、`signal_v`、`png`。
