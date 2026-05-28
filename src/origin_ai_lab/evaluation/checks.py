from __future__ import annotations

from math import isfinite

from origin_ai_lab.models import CheckResult, DatasetProfile, RegressionResult


def check_dataset_has_rows(profile: DatasetProfile) -> CheckResult:
    if profile.row_count > 0:
        return CheckResult("dataset_has_rows", True, f"{profile.row_count} rows detected.")
    return CheckResult("dataset_has_rows", False, "Dataset is empty.")


def check_columns_exist(profile: DatasetProfile, *columns: str) -> CheckResult:
    existing = {column.name for column in profile.columns}
    missing = [column for column in columns if column not in existing]
    if not missing:
        return CheckResult("columns_exist", True, "Required columns exist.")
    return CheckResult("columns_exist", False, f"Missing columns: {', '.join(missing)}")


def check_columns_numeric(profile: DatasetProfile, *columns: str) -> CheckResult:
    numeric = set(profile.numeric_columns())
    non_numeric = [column for column in columns if column not in numeric]
    if not non_numeric:
        return CheckResult("columns_numeric", True, "Required columns are numeric.")
    return CheckResult("columns_numeric", False, f"Non-numeric columns: {', '.join(non_numeric)}")


def check_regression_sane(result: RegressionResult) -> list[CheckResult]:
    checks = [
        CheckResult("regression_n", result.n >= 2, f"Regression used n={result.n}."),
        CheckResult(
            "regression_finite",
            all(isfinite(value) for value in (result.slope, result.intercept, result.r_squared)),
            "Regression coefficients are finite.",
        ),
        CheckResult(
            "regression_r2_range",
            0.0 <= result.r_squared <= 1.0,
            f"R2 is {result.r_squared:.6g}.",
        ),
    ]
    return checks
