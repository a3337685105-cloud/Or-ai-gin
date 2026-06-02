from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from origin_ai_lab.connectors.software_discovery import discover_comsol


@dataclass(frozen=True)
class ComsolCase:
    case_id: str
    title: str
    relative_path: Path
    study: str
    purpose: str
    acceptance: tuple[str, ...]
    category: str = "thermal"
    reference_url: str | None = None
    expected_metrics: dict[str, object] | None = None
    stage: int = 0
    golden_role: str = "smoke"
    physics: tuple[str, ...] = ()
    verification_targets: tuple[str, ...] = ()
    required_artifacts: tuple[str, ...] = ("solver_log", "solved_mph", "credibility_card")
    comparator: dict[str, object] | None = None
    risk_tags: tuple[str, ...] = ()

    def resolve_path(self, install_root: Path | None = None) -> Path | None:
        root = install_root or discover_comsol().install_path
        if root is None:
            return None
        path = root / "Multiphysics" / "applications" / self.relative_path
        return path if path.exists() else None

    def to_dict(self, install_root: Path | None = None) -> dict[str, object]:
        path = self.resolve_path(install_root)
        return {
            "case_id": self.case_id,
            "title": self.title,
            "category": self.category,
            "relative_path": str(self.relative_path),
            "resolved_path": str(path) if path else None,
            "available": path is not None,
            "study": self.study,
            "purpose": self.purpose,
            "acceptance": list(self.acceptance),
            "reference_url": self.reference_url,
            "expected_metrics": self.expected_metrics or {},
            "stage": self.stage,
            "golden_role": self.golden_role,
            "physics": list(self.physics),
            "verification_targets": list(self.verification_targets),
            "required_artifacts": list(self.required_artifacts),
            "comparator": self.comparator or {},
            "risk_tags": list(self.risk_tags),
        }


COMSOL_THERMAL_CASES: dict[str, ComsolCase] = {
    "busbar_smoke": ComsolCase(
        case_id="busbar_smoke",
        title="Electrical Heating in a Busbar",
        relative_path=Path("COMSOL_Multiphysics") / "Multiphysics" / "busbar.mph",
        study="std1",
        purpose="Fast local COMSOL batch, license, and solver smoke test.",
        acceptance=(
            "comsolbatch exits with code 0.",
            "Solver log reaches 100% completion.",
            "Solved MPH output file exists.",
        ),
        category="multiphysics_smoke",
        reference_url="https://www.comsol.com/model/electrical-heating-in-a-busbar-973",
        stage=0,
        golden_role="installation_and_solver_smoke",
        physics=("joule_heating", "conduction", "multiphysics"),
        verification_targets=("batch_execution", "solver_log_completion", "solved_model_artifact"),
        comparator={
            "type": "artifact_and_log",
            "required": {"return_code": 0, "solver_log_completed": True, "output_mph_exists": True},
        },
        risk_tags=("does_not_validate_custom_geometry", "does_not_extract_temperature_qoi_yet"),
    ),
    "thin_plate_verification": ComsolCase(
        case_id="thin_plate_verification",
        title="Out-of-Plane Heat Transfer for a Thin Plate",
        relative_path=Path("Heat_Transfer_Module") / "Verification_Examples" / "thin_plate.mph",
        study="std1",
        purpose="Verification-style heat-transfer model with documented 2D/3D profile comparison.",
        acceptance=(
            "Batch solve completes.",
            "The later exported 2D and 3D temperature profiles closely overlap as documented by COMSOL.",
        ),
        category="verification_conduction",
        reference_url="https://doc.comsol.com/6.4/doc/com.comsol.help.models.heat.thin_plate/thin_plate.html",
        stage=1,
        golden_role="official_verification_model",
        physics=("conduction", "out_of_plane_heat_transfer"),
        verification_targets=("2d_3d_temperature_profile_overlap", "temperature_field_shape"),
        comparator={
            "type": "profile_comparison",
            "qoi": "temperature_profile",
            "planned_tolerance": {"relative_rms_percent_max": 2.0},
            "automation_status": "requires_result_export",
        },
        risk_tags=("requires_profile_export", "selection_mapping_not_automated"),
    ),
    "slab_conduction_tutorial": ComsolCase(
        case_id="slab_conduction_tutorial",
        title="Heat Conduction in a Slab",
        relative_path=Path("Heat_Transfer_Module") / "Tutorials,_Conduction" / "heat_conduction_in_slab.mph",
        study="std1",
        purpose="Small conduction tutorial for checking basic thermal boundary setup and transient/steady interpretation.",
        acceptance=(
            "Batch solve completes.",
            "Later exported temperature profiles should follow the documented slab-conduction trend.",
        ),
        category="tutorial_conduction",
        reference_url="https://doc.comsol.com/6.4/doc/com.comsol.help.models.heat.heat_conduction_in_slab/heat_conduction_in_slab.html",
        stage=3,
        golden_role="tutorial_trend_benchmark",
        physics=("conduction", "slab_heat_transfer"),
        verification_targets=("profile_trend", "temperature_bounds", "transient_or_stationary_interpretation"),
        comparator={
            "type": "trend_and_bounds",
            "qoi": "temperature_profile",
            "planned_checks": ("monotonic_or_expected_shape", "finite_temperature_bounds"),
            "automation_status": "requires_result_export",
        },
        risk_tags=("qualitative_until_exported_profiles_are_available",),
    ),
    "cylinder_conduction_tutorial": ComsolCase(
        case_id="cylinder_conduction_tutorial",
        title="Cylinder Conduction",
        relative_path=Path("Heat_Transfer_Module") / "Tutorials,_Conduction" / "cylinder_conduction.mph",
        study="std1",
        purpose="Axisymmetric-style conduction tutorial useful for radial heat-transfer checks.",
        acceptance=(
            "Batch solve completes.",
            "Later exported radial temperature profile should be monotonic and physically bounded.",
        ),
        category="tutorial_conduction",
        reference_url="https://doc.comsol.com/6.4/doc/com.comsol.help.models.heat.cylinder_conduction/cylinder_conduction.html",
        stage=4,
        golden_role="tutorial_trend_benchmark",
        physics=("radial_conduction", "axisymmetric_heat_transfer"),
        verification_targets=("radial_temperature_profile", "temperature_bounds"),
        comparator={
            "type": "trend_and_bounds",
            "qoi": "radial_temperature_profile",
            "planned_checks": ("monotonic_radial_profile", "finite_temperature_bounds"),
            "automation_status": "requires_result_export",
        },
        risk_tags=("qualitative_until_exported_profiles_are_available",),
    ),
    "localized_heat_source_verification": ComsolCase(
        case_id="localized_heat_source_verification",
        title="Localized Heat Source",
        relative_path=Path("Heat_Transfer_Module") / "Verification_Examples" / "localized_heat_source.mph",
        study="std1",
        purpose="Verification-style localized source case for checking heat-source placement and peak-temperature behavior.",
        acceptance=(
            "Batch solve completes.",
            "Later exported peak temperature occurs near the localized source region.",
        ),
        category="verification_source",
        reference_url="https://doc.comsol.com/6.4/doc/com.comsol.help.models.heat.localized_heat_source/localized_heat_source.html",
        stage=5,
        golden_role="official_verification_model",
        physics=("localized_heat_source", "conduction"),
        verification_targets=("hotspot_location", "peak_temperature_behavior"),
        comparator={
            "type": "spatial_qoi",
            "qoi": "peak_temperature_location",
            "planned_checks": ("peak_near_source_region", "finite_temperature_bounds"),
            "automation_status": "requires_result_export",
        },
        risk_tags=("requires_peak_location_export",),
    ),
    "chip_cooling_reference": ComsolCase(
        case_id="chip_cooling_reference",
        title="Electronic Chip Cooling",
        relative_path=Path("Heat_Transfer_Module")
        / "Tutorials,_Forced_and_Natural_Convection"
        / "chip_cooling.mph",
        study="std1",
        purpose="Domain-relevant electronics cooling model for max-temperature extraction.",
        acceptance=(
            "Batch solve completes for the selected configuration.",
            "Extracted max chip temperatures are checked against documented reference values.",
        ),
        category="electronics_cooling",
        reference_url="https://doc.comsol.com/5.6/doc/com.comsol.help.models.heat.chip_cooling/chip_cooling.html",
        expected_metrics={
            "max_chip_temperature_C_reference_values": {
                "ideal_contact": 84,
                "air_layer": 95,
                "nonisothermal_flow": 90,
                "radiation": 80,
            }
        },
        stage=2,
        golden_role="domain_reference_benchmark",
        physics=("electronics_cooling", "conduction", "convection", "radiation_optional"),
        verification_targets=("max_chip_temperature", "configuration_comparison"),
        comparator={
            "type": "published_reference_values",
            "qoi": "max_chip_temperature_C",
            "planned_tolerance": {"absolute_error_C_max": 5.0},
            "reference_values_key": "max_chip_temperature_C_reference_values",
            "automation_status": "requires_qoi_export",
        },
        risk_tags=("multiple_configurations_need_explicit_selection", "requires_temperature_qoi_export"),
    ),
    "surface_mount_package_reference": ComsolCase(
        case_id="surface_mount_package_reference",
        title="Surface-Mount Package",
        relative_path=Path("Heat_Transfer_Module")
        / "Power_Electronics_and_Electronic_Cooling"
        / "surface_mount_package.mph",
        study="std1",
        purpose="Electronics package thermal model for broadening from chip cooling to package-level heat spreading.",
        acceptance=(
            "Batch solve completes.",
            "Later extracted package temperature and heat-flux metrics are finite and physically plausible.",
        ),
        category="electronics_cooling",
        reference_url="https://doc.comsol.com/6.4/doc/com.comsol.help.models.heat.surface_mount_package/surface_mount_package.html",
        stage=6,
        golden_role="domain_plausibility_benchmark",
        physics=("electronics_package", "heat_spreading", "conduction"),
        verification_targets=("package_temperature", "heat_flux_plausibility"),
        comparator={
            "type": "plausibility_bounds",
            "qoi": "package_temperature_and_heat_flux",
            "planned_checks": ("finite_temperature", "finite_heat_flux", "no_unphysical_signs"),
            "automation_status": "requires_qoi_export",
        },
        risk_tags=("package_stackup_assumptions_are_sensitive",),
    ),
    "thermal_contact_package_heat_sink": ComsolCase(
        case_id="thermal_contact_package_heat_sink",
        title="Thermal Contact, Electronic Package, and Heat Sink",
        relative_path=Path("Heat_Transfer_Module")
        / "Thermal_Contact_and_Friction"
        / "thermal_contact_electronic_package_heat_sink.mph",
        study="std1",
        purpose="Thermal-contact case for checking contact resistance assumptions in electronics cooling models.",
        acceptance=(
            "Batch solve completes.",
            "Later metrics should show a contact-driven temperature drop across the interface.",
        ),
        category="thermal_contact",
        reference_url=(
            "https://doc.comsol.com/6.4/doc/com.comsol.help.models.heat."
            "thermal_contact_electronic_package_heat_sink/thermal_contact_electronic_package_heat_sink.html"
        ),
        stage=7,
        golden_role="thermal_contact_risk_benchmark",
        physics=("thermal_contact", "electronics_cooling", "heat_sink"),
        verification_targets=("contact_temperature_drop", "contact_resistance_sensitivity"),
        comparator={
            "type": "interface_delta_temperature",
            "qoi": "temperature_drop_across_contact",
            "planned_checks": ("nonzero_contact_delta_when_resistance_enabled", "finite_temperature_bounds"),
            "automation_status": "requires_interface_qoi_export",
        },
        risk_tags=("contact_resistance_inputs_dominate_result", "requires_interface_selection_export"),
    ),
}


def get_comsol_case(case_id: str) -> ComsolCase:
    try:
        return COMSOL_THERMAL_CASES[case_id]
    except KeyError as exc:
        known = ", ".join(sorted(COMSOL_THERMAL_CASES))
        raise ValueError(f"Unknown COMSOL case {case_id!r}. Known cases: {known}.") from exc
