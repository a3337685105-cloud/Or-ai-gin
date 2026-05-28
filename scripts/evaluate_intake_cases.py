from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from origin_ai_lab.agents.planner_adapter import infer_requirement_auto
from origin_ai_lab.agents.requirement_intake import infer_requirement
from origin_ai_lab.connectors.csv_table import profile_csv


DEFAULT_FIELDS = ("kind", "plot_kind", "task_type", "x_column", "y_column", "group_column", "ready_to_execute")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate requirement-intake completion against chart cases.")
    parser.add_argument("--cases", default=str(ROOT / "examples" / "eval_cases.json"))
    parser.add_argument("--planner", choices=("rule", "auto", "qwen"), default="rule")
    parser.add_argument("--out", default=str(ROOT / "runs" / "evals" / "intake_eval_report.json"))
    args = parser.parse_args()

    os.environ["ORIGIN_AI_PLANNER"] = args.planner
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    results = [evaluate_case(case, args.planner) for case in cases]
    summary = {
        "planner": args.planner,
        "case_count": len(results),
        "field_accuracy": sum(item["field_score"] for item in results) / max(len(results), 1),
        "usable_rate": sum(1 for item in results if item["usable"]) / max(len(results), 1),
        "results": results,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def evaluate_case(case: dict[str, Any], planner: str) -> dict[str, Any]:
    profile = profile_csv(ROOT / case["dataset"])
    if planner == "rule":
        intent = infer_requirement(case["request"], profile)
    else:
        intent = infer_requirement_auto(case["request"], profile)
    actual = intent.to_dict()
    expected = case["expected"]

    field_results = {}
    fields = tuple(field for field in DEFAULT_FIELDS if field in expected)
    for field in fields:
        field_results[field] = actual.get(field) == expected.get(field)

    expected_outputs = set(expected.get("output_formats", []))
    actual_outputs = set(actual.get("output_formats", []))
    if "output_formats" in expected:
        field_results["output_formats"] = expected_outputs.issubset(actual_outputs)

    if "style" in expected:
        actual_style = actual.get("style", {})
        field_results["style"] = all(actual_style.get(key) == value for key, value in expected["style"].items())

    if "clarifying_fields" in expected:
        actual_fields = {item.get("field") for item in actual.get("clarifying_questions", [])}
        field_results["clarifying_fields"] = set(expected["clarifying_fields"]).issubset(actual_fields)

    score = sum(1 for ok in field_results.values() if ok) / len(field_results)
    usable = actual["ready_to_execute"] == expected["ready_to_execute"]
    if expected.get("ready_to_execute"):
        usable = usable and actual.get("x_column") == expected.get("x_column") and actual.get("y_column") == expected.get("y_column")

    return {
        "id": case["id"],
        "source": case["source"],
        "request": case["request"],
        "field_score": score,
        "usable": usable,
        "field_results": field_results,
        "expected": expected,
        "actual": actual,
    }


if __name__ == "__main__":
    raise SystemExit(main())
