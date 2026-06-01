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
    ),
}


def get_comsol_case(case_id: str) -> ComsolCase:
    try:
        return COMSOL_THERMAL_CASES[case_id]
    except KeyError as exc:
        known = ", ".join(sorted(COMSOL_THERMAL_CASES))
        raise ValueError(f"Unknown COMSOL case {case_id!r}. Known cases: {known}.") from exc
