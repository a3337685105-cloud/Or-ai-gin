from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from origin_ai_lab.models import AnalysisTask, TaskType
from origin_ai_lab.workflows.analyze_and_plot import run_analysis


def main() -> int:
    dataset = ROOT / "examples" / "sample_xy.csv"
    output_dir = ROOT / "runs" / "origin_smoke"
    task = AnalysisTask(
        dataset_path=dataset,
        goal="Smoke test Origin automation with a sample XY dataset.",
        task_type=TaskType.PLOT_XY,
        use_origin=True,
    )
    result = run_analysis(task, output_dir)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
