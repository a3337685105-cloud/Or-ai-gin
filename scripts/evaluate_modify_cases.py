from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from origin_ai_lab.agents.qwen_edit_planner import (
    infer_edit_plan_auto,
    infer_edit_plan_rule,
    infer_edit_plan_with_qwen,
)
from origin_ai_lab.connectors.csv_table import profile_csv
from origin_ai_lab.models import PlotKind, PlotSpec
from origin_ai_lab.plotting.spec_editor import PlotSpecValidationError, apply_edit_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--planner", choices=("rule", "qwen", "auto"), default="rule")
    parser.add_argument("--cases", default="examples/modify_cases.json")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    cases = json.loads((ROOT / args.cases).read_text(encoding="utf-8"))
    results = []
    for case in cases:
        dataset = ROOT / case["dataset"]
        profile = profile_csv(dataset)
        spec = PlotSpec(
            dataset_path=dataset,
            plot_kind=PlotKind.SCATTER,
            x_column="time_s",
            y_column="signal_v",
            title="signal_v vs time_s",
            x_title="time_s",
            y_title="signal_v",
            fit_enabled=True,
            output_formats=("png",),
        )
        if args.planner == "qwen":
            plan = infer_edit_plan_with_qwen(case["request"], spec, profile)
        elif args.planner == "auto":
            plan = infer_edit_plan_auto(case["request"], spec, profile)
        else:
            plan = infer_edit_plan_rule(case["request"], spec, profile)
        updated = None
        error = None
        if plan.ready_to_execute:
            try:
                updated = apply_edit_plan(spec, plan, profile)
            except PlotSpecValidationError as exc:
                error = str(exc)
        score = score_case(case["expected"], plan.ready_to_execute, updated)
        results.append(
            {
                "id": case["id"],
                "request": case["request"],
                "score": score,
                "error": error,
                "expected": case["expected"],
                "edit_plan": plan.to_dict(),
                "actual_spec": updated.to_dict() if updated else None,
            }
        )

    summary = {
        "planner": args.planner,
        "case_count": len(results),
        "field_accuracy": sum(item["score"] for item in results) / max(len(results), 1),
        "usable_rate": sum(1 for item in results if item["score"] == 1.0) / max(len(results), 1),
        "results": results,
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.out:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    print(text)
    return 0 if summary["usable_rate"] == 1.0 else 1


def score_case(expected: dict[str, Any], ready: bool, spec: PlotSpec | None) -> float:
    checks = []
    for key, value in expected.items():
        if key == "ready_to_execute":
            checks.append(ready == value)
            continue
        if spec is None:
            checks.append(False)
            continue
        checks.append(_lookup(spec.to_dict(), key) == value)
    return sum(1 for item in checks if item) / max(len(checks), 1)


def _lookup(data: dict[str, Any], dotted: str) -> Any:
    value: Any = data
    for part in dotted.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


if __name__ == "__main__":
    raise SystemExit(main())
