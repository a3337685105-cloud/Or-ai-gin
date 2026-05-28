from __future__ import annotations

import argparse
import json
from pathlib import Path

from origin_ai_lab.agents.planner_adapter import infer_requirement_auto
from origin_ai_lab.connectors.csv_table import profile_csv
from origin_ai_lab.models import AnalysisTask, TaskType
from origin_ai_lab.workflows.analyze_and_plot import run_analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="origin-ai")
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser("analyze", help="Run the first CSV analysis workflow.")
    analyze.add_argument("dataset", type=Path)
    analyze.add_argument("--out", type=Path, default=Path("runs/demo"))
    analyze.add_argument("--x", dest="x_column")
    analyze.add_argument("--y", dest="y_column")
    analyze.add_argument("--goal", default="Create an XY analysis and plot specification.")
    analyze.add_argument("--no-origin", action="store_true", help="Skip Origin automation even if available.")
    analyze.add_argument("--task-type", choices=[item.value for item in TaskType], default=TaskType.PLOT_XY.value)

    intake = subparsers.add_parser("intake", help="Interpret a natural-language plotting request.")
    intake.add_argument("request")
    intake.add_argument("--dataset", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "intake":
        profile = profile_csv(args.dataset) if args.dataset else None
        intent = infer_requirement_auto(args.request, profile)
        print(json.dumps(intent.to_dict(), ensure_ascii=False, indent=2))
        return 0 if intent.ready_to_execute else 2

    if args.command != "analyze":
        parser.print_help()
        return 1

    task = AnalysisTask(
        dataset_path=args.dataset,
        goal=args.goal,
        task_type=TaskType(args.task_type),
        x_column=args.x_column,
        y_column=args.y_column,
        use_origin=not args.no_origin,
    )
    result = run_analysis(task, args.out)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
