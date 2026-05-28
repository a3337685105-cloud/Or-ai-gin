# 视觉质量检验设计

## 当前边界

之前的检验主要覆盖数据和规格准确性：列是否存在、列是否为数值、回归结果是否有限、route/spec 是否可复现。它能证明“画的是对的数据列”，但不能证明“导出的图真的可见、没空白、没裁切、视觉上可用”。

## MVP 视觉 QA

当前新增的视觉检验是确定性后处理，不让 AI 直接判定通过与否：

- `visual_image_exists`：图片产物存在。
- `visual_dimensions`：分辨率达到最低目标，低于目标先作为 warning。
- `visual_nonblank`：采样颜色数量和非背景像素比例足够，防止空白图。
- `visual_content_visible`：内容包围盒面积足够，防止只有边框或极少像素。
- `visual_contrast`：亮度标准差足够，防止浅色线条几乎不可见。
- `visual_not_clipped`：内容没有贴边到完全裁切，先作为 warning。

每次 Origin 产出 PNG 后，系统会生成 `visual_quality.json`，并把视觉检查写入 `result.json` 的 checks。

## 后续增强

1. 图像语义检查：确认轴标题、图例、拟合线、误差棒、峰标注等是否出现。
2. 图像-规格对齐：把 `PlotSpec` 和图像检测结果对齐，判断 scatter/line/bar/hist 是否符合。
3. 图像审美评分：在确定性检查通过后，引入 AI critic 评估论文图风格、配色、字体和排版，但只作为建议或 warning。
4. 参考图对比：对公开 benchmark 或模板图做视觉相似度/结构相似度检查。
