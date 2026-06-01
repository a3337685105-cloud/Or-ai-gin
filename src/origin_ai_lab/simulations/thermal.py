from __future__ import annotations

from origin_ai_lab.models import (
    CheckResult,
    SimulationParameter,
    ThermalSimulationSpec,
    ThermalSimulationTask,
)


DEFAULT_THERMAL_PARAMETERS: dict[str, tuple[float, str, tuple[float | None, float | None], str]] = {
    "chip_power_W": (5.0, "W", (0.0, 10000.0), "Default heat source power for the first dry thermal template."),
    "ambient_temp_C": (25.0, "degC", (-273.15, 1000.0), "Default room-temperature ambient boundary."),
    "h_conv_W_m2K": (10.0, "W/(m^2*K)", (0.01, 100000.0), "Default natural-convection coefficient."),
    "cooling_area_m2": (0.01, "m^2", (0.000001, 1000.0), "Default exposed cooling area for mock calculations."),
    "base_resistance_K_W": (2.0, "K/W", (0.0, 100000.0), "Lumped conduction/contact resistance used by the mock solver."),
}

REQUIRED_THERMAL_PARAMETERS = ("chip_power_W", "ambient_temp_C", "h_conv_W_m2K")


def build_thermal_spec(task: ThermalSimulationTask) -> ThermalSimulationSpec:
    parameters: list[SimulationParameter] = []
    assumptions: list[str] = []
    for name, (default_value, unit, _limits, assumption) in DEFAULT_THERMAL_PARAMETERS.items():
        if name in task.parameters:
            parameters.append(SimulationParameter(name=name, value=float(task.parameters[name]), unit=unit, source="user"))
        else:
            parameters.append(SimulationParameter(name=name, value=default_value, unit=unit, source="default"))
            assumptions.append(assumption)

    for name, value in sorted(task.parameters.items()):
        if name not in DEFAULT_THERMAL_PARAMETERS:
            parameters.append(SimulationParameter(name=name, value=float(value), unit=None, source="user"))

    if task.template_path is None:
        assumptions.append("No COMSOL .mph template was supplied; only mock or dry-run execution is available.")

    return ThermalSimulationSpec(
        source_request=task.goal,
        template_id=task.template_id,
        template_path=task.template_path,
        backend=task.backend,
        study_type=task.study_type,
        parameters=tuple(parameters),
        outputs=task.outputs,
        assumptions=tuple(assumptions),
    )


def validate_thermal_spec(spec: ThermalSimulationSpec) -> list[CheckResult]:
    values = spec.parameter_map()
    checks: list[CheckResult] = []

    missing = [name for name in REQUIRED_THERMAL_PARAMETERS if name not in values]
    checks.append(
        CheckResult(
            name="thermal_required_parameters",
            passed=not missing,
            message="Required thermal parameters are present." if not missing else f"Missing parameters: {', '.join(missing)}.",
        )
    )

    for name, (_default, _unit, limits, _assumption) in DEFAULT_THERMAL_PARAMETERS.items():
        if name not in values:
            continue
        lower, upper = limits
        value = values[name]
        in_range = (lower is None or value >= lower) and (upper is None or value <= upper)
        checks.append(
            CheckResult(
                name=f"thermal_parameter_range:{name}",
                passed=in_range,
                message=(
                    f"{name}={value:g} is inside the allowed range."
                    if in_range
                    else f"{name}={value:g} is outside the allowed range {lower}..{upper}."
                ),
            )
        )

    if spec.backend.value == "comsol":
        template_ok = spec.template_path is not None and spec.template_path.exists()
        checks.append(
            CheckResult(
                name="comsol_template_available",
                passed=template_ok,
                message=(
                    f"COMSOL template found at {spec.template_path}."
                    if template_ok
                    else "COMSOL backend requires an existing .mph template path."
                ),
            )
        )
    else:
        checks.append(
            CheckResult(
                name="comsol_template_available",
                passed=True,
                message="COMSOL template is optional for mock and dry-run execution.",
                severity="warning",
            )
        )

    checks.append(
        CheckResult(
            name="thermal_outputs_declared",
            passed=bool(spec.outputs),
            message="Requested thermal outputs are declared." if spec.outputs else "At least one thermal output must be declared.",
        )
    )
    return checks


def build_thermal_execution_plan(spec: ThermalSimulationSpec) -> dict[str, object]:
    return {
        "schema_version": "thermal-execution-plan/v1",
        "backend": spec.backend.value,
        "template_id": spec.template_id,
        "template_path": str(spec.template_path) if spec.template_path else None,
        "study_type": spec.study_type,
        "steps": [
            {
                "id": "load_template",
                "tool": "comsol" if spec.backend.value == "comsol" else spec.backend.value,
                "description": "Load the validated thermal model template.",
            },
            {
                "id": "set_parameters",
                "tool": "model_parameters",
                "parameters": [parameter.to_dict() for parameter in spec.parameters],
            },
            {
                "id": "run_study",
                "tool": "thermal_solver",
                "study_type": spec.study_type,
                "description": "Run the stationary thermal study or record a dry-run plan.",
            },
            {
                "id": "export_results",
                "tool": "artifact_writer",
                "outputs": list(spec.outputs),
            },
        ],
        "guardrails": [
            "AI may only change declared parameters.",
            "A real COMSOL run must use a prevalidated .mph template.",
            "Solver convergence and physical sanity checks must be written to result.json.",
        ],
    }


def run_mock_thermal_solver(spec: ThermalSimulationSpec) -> dict[str, object]:
    values = spec.parameter_map()
    power_w = values["chip_power_W"]
    ambient_c = values["ambient_temp_C"]
    h_conv = values["h_conv_W_m2K"]
    area = values["cooling_area_m2"]
    base_resistance = values["base_resistance_K_W"]

    conv_resistance = 1.0 / (h_conv * area)
    total_resistance = base_resistance + conv_resistance
    delta_t = power_w * total_resistance
    max_temp_c = ambient_c + delta_t

    return {
        "solver": "mock_lumped_thermal_resistance",
        "solver_converged": True,
        "chip_power_W": round(power_w, 6),
        "ambient_temp_C": round(ambient_c, 6),
        "h_conv_W_m2K": round(h_conv, 6),
        "cooling_area_m2": round(area, 9),
        "convective_resistance_K_W": round(conv_resistance, 6),
        "base_resistance_K_W": round(base_resistance, 6),
        "total_resistance_K_W": round(total_resistance, 6),
        "temperature_rise_K": round(delta_t, 6),
        "max_temperature_C": round(max_temp_c, 6),
        "energy_balance_error_percent": 0.0,
    }


def evaluate_thermal_metrics(metrics: dict[str, object]) -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.append(
        CheckResult(
            name="thermal_solver_converged",
            passed=bool(metrics.get("solver_converged")),
            message="Thermal solver reported convergence." if metrics.get("solver_converged") else "Thermal solver did not converge.",
        )
    )
    if "max_temperature_C" in metrics:
        max_temp = float(metrics.get("max_temperature_C", 0.0))
        checks.append(
            CheckResult(
                name="thermal_max_temperature_recorded",
                passed=max_temp > -273.15,
                message=f"Maximum temperature is {max_temp:g} degC.",
            )
        )
    else:
        max_temp = None
        checks.append(
            CheckResult(
                name="thermal_max_temperature_recorded",
                passed=True,
                message="Maximum temperature extraction is not wired for this backend yet.",
                severity="warning",
            )
        )
    if max_temp is not None and max_temp > 120.0:
        checks.append(
            CheckResult(
                name="thermal_temperature_high",
                passed=False,
                message=f"Maximum temperature {max_temp:g} degC exceeds the initial 120 degC warning threshold.",
                severity="warning",
            )
        )
    return checks
