# AI 接入说明

## 当前状态

项目现在有两种 Planner：

- `rule`：规则版需求收束器，默认可离线运行。
- `qwen`：阿里云百炼/通义千问 OpenAI-compatible 适配器。

默认模式是 `auto`：如果环境变量里存在 `DASHSCOPE_API_KEY`，优先走千问；否则自动回落到规则版。

## 官方接入依据

阿里云百炼官方文档说明，Model Studio 支持通过 OpenAI-compatible interface 和 DashScope SDK 调用模型。官方示例使用 `DASHSCOPE_API_KEY` 环境变量，并把 `base_url` 指向 `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`；中国北京地域的 OpenAI-compatible 地址是 `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`。

你确认账户里可用 `qwen3.7-max` 后，当前代码默认使用 `qwen3.7-max`。如果后续要切换模型，可通过 `QWEN_MODEL` 覆盖。

## 环境变量

```powershell
$env:ORIGIN_AI_PLANNER = "qwen"
$env:DASHSCOPE_API_KEY = "<your key>"
$env:QWEN_MODEL = "qwen3.7-max"
$env:QWEN_ENABLE_THINKING = "true"
$env:QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

说明：

- `DASHSCOPE_API_KEY`：必需。不要写入仓库。
- `QWEN_MODEL`：默认 `qwen3.7-max`。
- `QWEN_ENABLE_THINKING`：默认 `true`，对应百炼请求体里的 `enable_thinking`。
- `QWEN_BASE_URL`：默认中国北京地域。不同地域 key 和 endpoint 不能混用。
- `ORIGIN_AI_PLANNER`：`auto`、`rule`、`qwen`。

## 代码落点

- `src/origin_ai_lab/agents/qwen_planner.py`：千问适配器。
- `src/origin_ai_lab/agents/planner_adapter.py`：自动选择规则版或千问。
- `scripts/qwen_smoke_test.py`：千问真实调用烟测。
- `scripts/evaluate_intake_cases.py`：需求理解用例评测。

## 调用方式

千问烟测：

```powershell
python scripts\qwen_smoke_test.py --model qwen3.7-max
```

评测需求理解完成度：

```powershell
python scripts\evaluate_intake_cases.py --planner rule
python scripts\evaluate_intake_cases.py --planner qwen
```

Web UI：

```powershell
$env:ORIGIN_AI_PLANNER = "auto"
$env:PYTHONPATH = "src"
python -m origin_ai_lab.web_server
```

打开 `http://127.0.0.1:8765` 后，在“千问设置”区域填写并保存 key。保存后 key 会写入本机用户目录的 DPAPI 加密密钥仓库，页面不会回显明文。

## 安全边界

模型只输出 `RequirementIntent`，不能直接操作 Origin。后端仍然要做：

- 列名存在性检查。
- 参数范围检查。
- 是否需要追问。
- 是否允许覆盖文件。
- 是否调用 Origin。

这保证以后更换模型不会改变执行层的安全边界。
