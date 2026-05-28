from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from origin_ai_lab.agents.qwen_planner import (
    DEFAULT_QWEN_BASE_URL,
    DEFAULT_QWEN_MODEL,
    QwenConfig,
    QwenPlannerError,
    infer_requirement_with_qwen,
    qwen_status,
)
from origin_ai_lab.connectors.csv_table import profile_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test Alibaba Cloud Model Studio / Qwen planner.")
    parser.add_argument("--dataset", default=str(ROOT / "examples" / "sample_xy.csv"))
    parser.add_argument("--request", default="帮我画散点图，加线性拟合，导出 png")
    parser.add_argument("--model", default=os.getenv("QWEN_MODEL", DEFAULT_QWEN_MODEL))
    parser.add_argument("--base-url", default=os.getenv("QWEN_BASE_URL", DEFAULT_QWEN_BASE_URL))
    args = parser.parse_args()

    status = qwen_status()
    if not status["configured"]:
        print(json.dumps({"status": "skipped", "reason": "DASHSCOPE_API_KEY is not set."}, ensure_ascii=False, indent=2))
        return 0

    saved_config = QwenConfig.from_env()
    if saved_config is None:
        print(json.dumps({"status": "skipped", "reason": "DASHSCOPE_API_KEY or saved key is not set."}, ensure_ascii=False, indent=2))
        return 0

    config = QwenConfig(
        api_key=saved_config.api_key,
        base_url=args.base_url,
        model=args.model,
        enable_thinking=saved_config.enable_thinking,
        key_source=saved_config.key_source,
    )
    profile = profile_csv(Path(args.dataset))
    try:
        intent = infer_requirement_with_qwen(args.request, profile, config)
    except QwenPlannerError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "model": args.model,
                    "base_url": args.base_url,
                    "enable_thinking": config.enable_thinking,
                    "key_source": config.key_source,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    print(
        json.dumps(
            {
                "status": "ok",
                "model": args.model,
                "base_url": args.base_url,
                "enable_thinking": config.enable_thinking,
                "key_source": config.key_source,
                "intent": intent.to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if intent.ready_to_execute else 1


if __name__ == "__main__":
    raise SystemExit(main())
