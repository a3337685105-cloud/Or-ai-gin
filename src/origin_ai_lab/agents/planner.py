from __future__ import annotations

from origin_ai_lab.agents.requirement_intake import infer_requirement
from origin_ai_lab.models import AnalysisTask, DatasetProfile, TaskType


def choose_xy_columns(profile: DatasetProfile, requested_x: str | None, requested_y: str | None) -> tuple[str, str]:
    numeric_columns = profile.numeric_columns()
    if requested_x and requested_y:
        return requested_x, requested_y
    if len(numeric_columns) < 2:
        raise ValueError("At least two numeric columns are required for an XY workflow.")
    return requested_x or numeric_columns[0], requested_y or numeric_columns[1]


def plan_task(profile: DatasetProfile, task: AnalysisTask) -> dict[str, object]:
    requirement = infer_requirement(task.goal, profile)
    x_column, y_column = choose_xy_columns(profile, task.x_column, task.y_column)
    return {
        "task_type": task.task_type.value,
        "goal": task.goal,
        "requirement_intent": requirement.to_dict(),
        "dataset_path": str(task.dataset_path),
        "x_column": x_column,
        "y_column": y_column,
        "use_origin": task.use_origin,
        "tools": [
            "profile_dataset",
            "run_linear_regression" if task.task_type in {TaskType.REGRESSION, TaskType.PLOT_XY} else "describe_dataset",
            "validate_result",
            "export_artifacts",
        ],
        "assumptions": [
            "The first two numeric columns are used as X/Y when the user does not specify columns.",
            "The MVP uses ordinary least squares for the regression workflow.",
        ],
    }
