from __future__ import annotations

from math import fsum
from pathlib import Path

from origin_ai_lab.connectors.csv_table import numeric_pairs
from origin_ai_lab.models import RegressionResult


def linear_regression_from_csv(path: Path, x_column: str, y_column: str) -> RegressionResult:
    pairs = numeric_pairs(path, x_column, y_column)
    if len(pairs) < 2:
        raise ValueError("Linear regression requires at least two rows.")

    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    n = len(pairs)
    mean_x = fsum(xs) / n
    mean_y = fsum(ys) / n
    ss_xx = fsum((x - mean_x) ** 2 for x in xs)
    if ss_xx == 0:
        raise ValueError("X column has zero variance.")

    ss_xy = fsum((x - mean_x) * (y - mean_y) for x, y in pairs)
    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x
    predictions = [slope * x + intercept for x in xs]
    ss_res = fsum((y - y_hat) ** 2 for y, y_hat in zip(ys, predictions))
    ss_tot = fsum((y - mean_y) ** 2 for y in ys)
    r_squared = 1.0 if ss_tot == 0 else 1.0 - (ss_res / ss_tot)

    return RegressionResult(
        x_column=x_column,
        y_column=y_column,
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        n=n,
    )
