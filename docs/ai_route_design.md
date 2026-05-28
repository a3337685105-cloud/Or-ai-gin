# AI 路由层设计

## 方案比较

### 方案 A：纯规则脚本

优点是确定、便宜、可测试，也最适合文件解析、数值列判断、格式导出等硬约束任务。缺点是真实仪器导出很杂，遇到多段数据、别名列名、语义省略时规则容易变脆。

### 方案 B：AI-first 路由

优点是语义弹性强，能理解“画热重”“做 Nyquist”“应力应变”这类自然说法。缺点是输出不确定、成本高、隐私风险更大，也不能直接信任它选择的列和方法。

### 方案 C：规则优先 + AI 兜底 + 验证器裁决

这是当前采用的方案。脚本先解析数据并给出确定性 `RouteDecision`；当规则低置信度、需要追问、或遇到未知材料语义时，才让 Qwen 输出结构化路由建议。AI 建议必须经过列存在、数值比例、图类型和导出格式校验，不能直接执行 Origin 或修改项目。

## 当前实现

- `RouteDecision`：记录 route、planner、confidence、instrument_family、plot_kind、x/y/group 列、assumptions、warnings 和 clarifying_questions。
- `route_dataset_rule()`：确定性路由，覆盖 XRD、Raman、TGA、DSC、电池充放电、EIS/Nyquist、应力应变、粒径分布。
- `route_dataset_auto()`：默认先走规则；仅在规则需要补足时使用 Qwen。可用 `ORIGIN_AI_ROUTE_PLANNER=rule|auto|qwen` 切换。
- `run_analysis()`：每次分析都会写出 `route_decision.json` 和 `normalized_data.csv`，Origin 导入清洗后的 CSV。

## 安全边界

- AI 只做路由建议，不读写 Origin、不执行 LabTalk、不改 OPJU。
- AI 返回的列名必须存在于 `DatasetProfile`；不存在则转成追问。
- 离线/无 key 时规则路径仍可工作。
- 路由结果随 run artifact 保存，便于复现和审计。
