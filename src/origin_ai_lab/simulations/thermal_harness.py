from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from origin_ai_lab.connectors.software_discovery import discover_comsol
from origin_ai_lab.models import CheckResult, SimulationBackend, ThermalSimulationTask
from origin_ai_lab.simulations.comsol_cases import COMSOL_THERMAL_CASES
from origin_ai_lab.workflows.thermal_simulation import run_thermal_simulation


ALLOWED_GEOMETRY_TYPES = {"block", "sphere", "cylinder"}
ALLOWED_BOUNDARY_TYPES = {"convection", "fixed_temperature", "insulation", "heat_flux", "symmetry"}
ALLOWED_HEAT_SOURCE_TYPES = {"total_power", "volumetric_heat", "boundary_heat_flux"}
REQUIRED_MATERIAL_PROPS = ("thermal_conductivity_W_mK",)


def thermal_model_schema() -> dict[str, Any]:
    return {
        "schema_version": "thermal-model-proposal/v1",
        "goal": "One-sentence physical objective.",
        "geometry": [
            {
                "id": "base",
                "type": "block",
                "size_m": [0.05, 0.05, 0.003],
                "center_m": [0.0, 0.0, 0.0],
            },
            {
                "id": "hot_spot",
                "type": "sphere",
                "radius_m": 0.002,
                "center_m": [0.0, 0.0, 0.002],
            },
        ],
        "materials": [
            {
                "id": "aluminum",
                "thermal_conductivity_W_mK": 205,
                "density_kg_m3": 2700,
                "heat_capacity_J_kgK": 900,
            }
        ],
        "assignments": [{"geometry_id": "base", "material_id": "aluminum"}],
        "heat_sources": [{"id": "chip_power", "type": "total_power", "target": "hot_spot", "value_W": 5}],
        "boundary_conditions": [
            {
                "id": "ambient_convection",
                "type": "convection",
                "target": "outer_surfaces",
                "h_W_m2K": 10,
                "ambient_temp_C": 25,
            }
        ],
        "mesh": {"policy": "physics_controlled_normal"},
        "study": {"type": "stationary"},
        "observables": ["max_temperature_C", "temperature_field", "energy_balance"],
        "assumptions": ["All dimensions are SI meters.", "The geometry is a first-pass abstraction."],
    }


def example_thermal_model_proposal() -> dict[str, Any]:
    return {
        "schema_version": "thermal-model-proposal/v1",
        "goal": "Estimate steady-state temperature rise of a small heated chip on an aluminum plate.",
        "geometry": [
            {
                "id": "plate",
                "type": "block",
                "size_m": [0.05, 0.05, 0.003],
                "center_m": [0, 0, 0],
            },
            {
                "id": "chip",
                "type": "block",
                "size_m": [0.01, 0.01, 0.001],
                "center_m": [0, 0, 0.002],
            },
            {
                "id": "sensor_probe",
                "type": "sphere",
                "radius_m": 0.001,
                "center_m": [0.015, 0, 0.003],
            },
        ],
        "materials": [
            {
                "id": "aluminum",
                "thermal_conductivity_W_mK": 205,
                "density_kg_m3": 2700,
                "heat_capacity_J_kgK": 900,
            },
            {
                "id": "silicon",
                "thermal_conductivity_W_mK": 130,
                "density_kg_m3": 2330,
                "heat_capacity_J_kgK": 700,
            },
        ],
        "assignments": [
            {"geometry_id": "plate", "material_id": "aluminum"},
            {"geometry_id": "chip", "material_id": "silicon"},
            {"geometry_id": "sensor_probe", "material_id": "silicon"},
        ],
        "heat_sources": [{"id": "chip_heat", "type": "total_power", "target": "chip", "value_W": 5}],
        "boundary_conditions": [
            {
                "id": "ambient_convection",
                "type": "convection",
                "target": "all_exterior_surfaces",
                "h_W_m2K": 10,
                "ambient_temp_C": 25,
            }
        ],
        "mesh": {"policy": "physics_controlled_normal"},
        "study": {"type": "stationary"},
        "observables": ["max_temperature_C", "temperature_at_sensor_probe_C", "energy_balance"],
        "assumptions": [
            "The sensor_probe sphere is an observation marker, not a separate thermal mass in the final COMSOL model.",
            "The first generated model should be reviewed before solver execution.",
        ],
    }


def validate_thermal_model_proposal(proposal: dict[str, Any]) -> list[CheckResult]:
    checks: list[CheckResult] = []
    geometry = _list_of_dicts(proposal.get("geometry"))
    materials = _list_of_dicts(proposal.get("materials"))
    assignments = _list_of_dicts(proposal.get("assignments"))
    heat_sources = _list_of_dicts(proposal.get("heat_sources"))
    boundary_conditions = _list_of_dicts(proposal.get("boundary_conditions"))
    observables = proposal.get("observables") if isinstance(proposal.get("observables"), list) else []

    checks.append(
        CheckResult(
            name="model_schema_version",
            passed=proposal.get("schema_version") == "thermal-model-proposal/v1",
            message="Thermal model proposal schema version is supported.",
        )
    )
    checks.append(
        CheckResult(
            name="model_geometry_present",
            passed=bool(geometry),
            message="At least one geometry primitive is declared." if geometry else "No geometry primitives were declared.",
        )
    )

    geometry_ids: set[str] = set()
    for primitive in geometry:
        primitive_id = str(primitive.get("id") or "")
        primitive_type = str(primitive.get("type") or "")
        geometry_ids.add(primitive_id)
        checks.append(
            CheckResult(
                name=f"geometry_type:{primitive_id or 'missing'}",
                passed=primitive_type in ALLOWED_GEOMETRY_TYPES,
                message=f"{primitive_id or 'geometry'} uses supported primitive type {primitive_type!r}.",
            )
        )
        checks.append(_check_geometry_dimensions(primitive))

    material_ids = {str(material.get("id") or "") for material in materials}
    checks.append(
        CheckResult(
            name="materials_present",
            passed=bool(materials),
            message="At least one material is declared." if materials else "No materials were declared.",
        )
    )
    for material in materials:
        material_id = str(material.get("id") or "missing")
        missing_props = [prop for prop in REQUIRED_MATERIAL_PROPS if _number_from(material.get(prop)) is None]
        checks.append(
            CheckResult(
                name=f"material_properties:{material_id}",
                passed=not missing_props,
                message=(
                    f"{material_id} has required thermal material properties."
                    if not missing_props
                    else f"{material_id} is missing material properties: {', '.join(missing_props)}."
                ),
            )
        )

    assigned_geometry = {str(item.get("geometry_id") or "") for item in assignments}
    assigned_materials = {str(item.get("material_id") or "") for item in assignments}
    unassigned = sorted(item for item in geometry_ids if item and item not in assigned_geometry)
    unknown_materials = sorted(item for item in assigned_materials if item and item not in material_ids)
    checks.append(
        CheckResult(
            name="geometry_material_assignments",
            passed=not unassigned and not unknown_materials,
            message=(
                "Every geometry primitive has a known material assignment."
                if not unassigned and not unknown_materials
                else f"Unassigned geometry: {unassigned}; unknown materials: {unknown_materials}."
            ),
        )
    )

    checks.append(
        CheckResult(
            name="heat_sources_present",
            passed=bool(heat_sources),
            message="At least one heat source is declared." if heat_sources else "No heat source was declared.",
        )
    )
    for source in heat_sources:
        source_id = str(source.get("id") or "missing")
        source_type = str(source.get("type") or "")
        target = str(source.get("target") or "")
        checks.append(
            CheckResult(
                name=f"heat_source:{source_id}",
                passed=source_type in ALLOWED_HEAT_SOURCE_TYPES and (target in geometry_ids or target in {"all_domains"}),
                message=f"{source_id} has supported heat source type and target.",
            )
        )
        checks.append(_check_heat_source_value(source))

    checks.append(
        CheckResult(
            name="thermal_boundary_conditions_present",
            passed=bool(boundary_conditions),
            message=(
                "At least one thermal boundary condition is declared."
                if boundary_conditions
                else "No thermal boundary condition was declared."
            ),
        )
    )
    boundary_types = {str(item.get("type") or "") for item in boundary_conditions}
    for boundary in boundary_conditions:
        boundary_id = str(boundary.get("id") or "missing")
        boundary_type = str(boundary.get("type") or "")
        checks.append(
            CheckResult(
                name=f"boundary_type:{boundary_id}",
                passed=boundary_type in ALLOWED_BOUNDARY_TYPES,
                message=f"{boundary_id} uses supported boundary type {boundary_type!r}.",
            )
        )
    checks.append(
        CheckResult(
            name="thermal_sink_or_reference_present",
            passed=bool(boundary_types & {"convection", "fixed_temperature"}),
            message="A heat sink/reference boundary is present."
            if boundary_types & {"convection", "fixed_temperature"}
            else "Thermal model needs convection or fixed-temperature reference to avoid unconstrained heating.",
        )
    )

    checks.append(
        CheckResult(
            name="observables_declared",
            passed=bool(observables),
            message="Requested observables are declared." if observables else "No observables were declared.",
        )
    )
    return checks


def build_official_case_inventory(install_root: Path | None = None) -> list[dict[str, object]]:
    root = install_root
    if root is None:
        root = discover_comsol().install_path
    return [case.to_dict(root) for case in COMSOL_THERMAL_CASES.values()]


def run_thermal_harness(
    output_dir: Path,
    backend: SimulationBackend = SimulationBackend.DRY_RUN,
    case_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_case_ids = case_ids or tuple(sorted(COMSOL_THERMAL_CASES))
    schema = thermal_model_schema()
    proposal = example_thermal_model_proposal()
    proposal_checks = validate_thermal_model_proposal(proposal)
    install_root = discover_comsol().install_path
    inventory = build_official_case_inventory(install_root)
    selected_results: list[dict[str, Any]] = []

    _write_json(output_dir / "thermal_model_schema.json", schema)
    _write_json(output_dir / "example_model_proposal.json", proposal)
    _write_json(output_dir / "model_proposal_validation.json", _checks_to_dict(proposal_checks))
    _write_json(output_dir / "official_case_inventory.json", inventory)

    for case_id in selected_case_ids:
        case = COMSOL_THERMAL_CASES[case_id]
        case_dir = output_dir / "cases" / case.case_id
        case_path = case.resolve_path(install_root)
        if case_path is None:
            selected_results.append(
                {
                    "case_id": case.case_id,
                    "status": "missing",
                    "checks": [
                        CheckResult(
                            name="case_model_available",
                            passed=False,
                            message=f"COMSOL Application Library model not found for {case.case_id}.",
                        ).to_dict()
                    ],
                }
            )
            continue
        task = ThermalSimulationTask(
            goal=case.purpose,
            template_id=case.case_id,
            template_path=case_path,
            backend=backend,
            study_type=case.study,
        )
        result = run_thermal_simulation(task, case_dir)
        selected_results.append(
            {
                "case_id": case.case_id,
                "title": case.title,
                "status": result.status,
                "passed": result.passed,
                "result_path": result.artifacts.get("thermal_result"),
                "acceptance": list(case.acceptance),
            }
        )

    report = {
        "schema_version": "thermal-harness-report/v1",
        "backend": backend.value,
        "case_ids": list(selected_case_ids),
        "model_proposal_passed": all(check.passed for check in proposal_checks if check.severity == "error"),
        "case_results": selected_results,
        "artifacts": {
            "thermal_model_schema": str(output_dir / "thermal_model_schema.json"),
            "example_model_proposal": str(output_dir / "example_model_proposal.json"),
            "model_proposal_validation": str(output_dir / "model_proposal_validation.json"),
            "official_case_inventory": str(output_dir / "official_case_inventory.json"),
        },
    }
    _write_json(output_dir / "thermal_harness_report.json", report)
    return report


def comsol_geometry_api_examples() -> dict[str, str]:
    return {
        "java_block": (
            'model.geom("geom1").create("blk1", "Block");\n'
            'model.geom("geom1").feature("blk1").set("size", new String[]{"0.05", "0.05", "0.003"});\n'
            'model.geom("geom1").feature("blk1").set("pos", new String[]{"0", "0", "0"});'
        ),
        "java_sphere": (
            'model.geom("geom1").create("sph1", "Sphere");\n'
            'model.geom("geom1").feature("sph1").set("r", "0.002");\n'
            'model.geom("geom1").feature("sph1").set("pos", new String[]{"0", "0", "0.002"});'
        ),
        "matlab_block": (
            "model.geom('geom1').feature.create('blk1', 'Block');\n"
            "model.geom('geom1').feature('blk1').set('size', {'0.05','0.05','0.003'});\n"
            "model.geom('geom1').feature('blk1').set('pos', {'0','0','0'});"
        ),
        "matlab_sphere": (
            "model.geom('geom1').feature.create('sph1', 'Sphere');\n"
            "model.geom('geom1').feature('sph1').set('r', '0.002');\n"
            "model.geom('geom1').feature('sph1').set('pos', {'0','0','0.002'});"
        ),
    }


def _check_geometry_dimensions(primitive: dict[str, Any]) -> CheckResult:
    primitive_id = str(primitive.get("id") or "missing")
    primitive_type = str(primitive.get("type") or "")
    if primitive_type == "block":
        values = primitive.get("size_m")
        ok = isinstance(values, list) and len(values) == 3 and all(_positive_number(item) for item in values)
        message = "Block has three positive size_m values." if ok else "Block requires size_m=[x,y,z] with positive values."
    elif primitive_type == "sphere":
        ok = _positive_number(primitive.get("radius_m"))
        message = "Sphere has positive radius_m." if ok else "Sphere requires a positive radius_m."
    elif primitive_type == "cylinder":
        ok = _positive_number(primitive.get("radius_m")) and _positive_number(primitive.get("height_m"))
        message = "Cylinder has positive radius_m and height_m." if ok else "Cylinder requires positive radius_m and height_m."
    else:
        ok = False
        message = "Unsupported geometry type."
    return CheckResult(name=f"geometry_dimensions:{primitive_id}", passed=ok, message=message)


def _check_heat_source_value(source: dict[str, Any]) -> CheckResult:
    source_id = str(source.get("id") or "missing")
    source_type = str(source.get("type") or "")
    if source_type == "total_power":
        ok = _positive_number(source.get("value_W"))
        message = "Total-power heat source has positive value_W." if ok else "Total-power source requires positive value_W."
    elif source_type == "volumetric_heat":
        ok = _positive_number(source.get("value_W_m3"))
        message = (
            "Volumetric heat source has positive value_W_m3."
            if ok
            else "Volumetric source requires positive value_W_m3."
        )
    elif source_type == "boundary_heat_flux":
        ok = _positive_number(source.get("value_W_m2"))
        message = (
            "Boundary heat-flux source has positive value_W_m2."
            if ok
            else "Boundary heat-flux source requires positive value_W_m2."
        )
    else:
        ok = False
        message = "Unsupported heat source type."
    return CheckResult(name=f"heat_source_value:{source_id}", passed=ok, message=message)


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _number_from(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive_number(value: Any) -> bool:
    number = _number_from(value)
    return number is not None and number > 0


def _checks_to_dict(checks: list[CheckResult]) -> dict[str, Any]:
    return {
        "passed": all(check.passed for check in checks if check.severity == "error"),
        "checks": [check.to_dict() for check in checks],
    }


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
