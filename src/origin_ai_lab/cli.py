from __future__ import annotations

import argparse
import json
from pathlib import Path

from origin_ai_lab.agents.planner_adapter import infer_requirement_auto
from origin_ai_lab.agents.research_intake_harness import build_research_work_order, intake_question_bank
from origin_ai_lab.connectors.csv_table import profile_csv
from origin_ai_lab.connectors.software_discovery import discover_all
from origin_ai_lab.models import AnalysisTask, SimulationBackend, TaskType, ThermalSimulationTask
from origin_ai_lab.simulations.comsol_cases import COMSOL_THERMAL_CASES, get_comsol_case
from origin_ai_lab.simulations.thermal_harness import run_thermal_harness
from origin_ai_lab.workflows.analyze_and_plot import run_analysis
from origin_ai_lab.workflows.thermal_simulation import run_thermal_simulation


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

    research_intake = subparsers.add_parser("research-intake", help="Build a thick-to-thin research work order.")
    research_intake.add_argument("request", nargs="?")
    research_intake.add_argument("--answers-json", type=Path, help="Optional JSON file with collected user answers.")
    research_intake.add_argument("--question-bank", action="store_true", help="Print the guided intake question bank.")

    subparsers.add_parser("doctor", help="Discover local Origin and COMSOL installations.")

    thermal = subparsers.add_parser("thermal", help="Plan or run a thermal simulation scaffold.")
    thermal.add_argument("--goal", default="Run a stationary thermal simulation from a validated template.")
    thermal.add_argument("--out", type=Path, default=Path("runs/thermal_demo"))
    thermal.add_argument("--backend", choices=[item.value for item in SimulationBackend], default=SimulationBackend.MOCK.value)
    thermal.add_argument("--template-id", default="generic_stationary_heat")
    thermal.add_argument("--template", type=Path, help="Path to a validated COMSOL .mph thermal template.")
    thermal.add_argument("--case", choices=sorted(COMSOL_THERMAL_CASES), help="Use a registered official COMSOL test case.")
    thermal.add_argument("--study", default="stationary", help="COMSOL study tag such as std1, or a descriptive study type.")
    thermal.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="Thermal parameter override, for example chip_power_W=5.",
    )

    harness = subparsers.add_parser("thermal-harness", help="Build and run the thermal modeling validation harness.")
    harness.add_argument("--out", type=Path, default=Path("runs/thermal_harness"))
    harness.add_argument("--backend", choices=[item.value for item in SimulationBackend], default=SimulationBackend.DRY_RUN.value)
    harness.add_argument(
        "--case",
        choices=sorted(COMSOL_THERMAL_CASES),
        action="append",
        default=[],
        help="Official COMSOL case to include. May be repeated. Defaults to all registered cases.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "intake":
        profile = profile_csv(args.dataset) if args.dataset else None
        intent = infer_requirement_auto(args.request, profile)
        print(json.dumps(intent.to_dict(), ensure_ascii=False, indent=2))
        return 0 if intent.ready_to_execute else 2

    if args.command == "research-intake":
        if args.question_bank:
            print(json.dumps({"schema_version": "research-intake-question-bank/v1", "questions": intake_question_bank()}, ensure_ascii=False, indent=2))
            return 0
        if not args.request:
            raise SystemExit("research-intake requires a request unless --question-bank is used.")
        answers = {}
        if args.answers_json:
            answers = json.loads(args.answers_json.read_text(encoding="utf-8"))
            if not isinstance(answers, dict):
                raise SystemExit("--answers-json must contain a JSON object.")
        work_order = build_research_work_order(args.request, answers)
        print(json.dumps(work_order.to_dict(), ensure_ascii=False, indent=2))
        return 0 if work_order.ready_to_plan else 2

    if args.command == "doctor":
        installs = discover_all()
        print(json.dumps({key: value.to_dict() for key, value in installs.items()}, ensure_ascii=False, indent=2))
        return 0 if all(install.found for install in installs.values()) else 2

    if args.command == "thermal":
        template_path = args.template
        study = args.study
        template_id = args.template_id
        if args.case:
            case = get_comsol_case(args.case)
            template_path = template_path or case.resolve_path()
            if template_path is None:
                raise SystemExit(f"Registered COMSOL case {args.case!r} was not found in the local Application Library.")
            if args.study == "stationary":
                study = case.study
            if args.template_id == "generic_stationary_heat":
                template_id = case.case_id
        task = ThermalSimulationTask(
            goal=args.goal,
            template_id=template_id,
            template_path=template_path,
            backend=SimulationBackend(args.backend),
            parameters=_parse_parameters(args.param),
            study_type=study,
        )
        result = run_thermal_simulation(task, args.out)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0 if result.passed else 2

    if args.command == "thermal-harness":
        report = run_thermal_harness(
            output_dir=args.out,
            backend=SimulationBackend(args.backend),
            case_ids=tuple(args.case),
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("model_proposal_passed") else 2

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


def _parse_parameters(items: list[str]) -> dict[str, float]:
    parameters: dict[str, float] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"Invalid --param value {item!r}; expected NAME=VALUE.")
        name, raw_value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise SystemExit(f"Invalid --param value {item!r}; parameter name is empty.")
        try:
            parameters[name] = float(raw_value.strip())
        except ValueError as exc:
            raise SystemExit(f"Invalid --param value {item!r}; value must be numeric.") from exc
    return parameters


if __name__ == "__main__":
    raise SystemExit(main())
