from __future__ import annotations

from pathlib import Path
from typing import Any

from origin_ai_lab.models import CheckResult, ThermalSimulationSpec, VisualizationSpec, VisualizationViewSpec


DEFAULT_THERMAL_VIEW_IDS: tuple[str, ...] = (
    "temperature_overview",
    "key_slice",
    "isotherm_threshold",
    "heat_flux_view",
    "probe_path_curves",
    "parameter_comparison",
    "animation_manifest",
)

THERMAL_VISUAL_QUALITY_RULES: tuple[dict[str, str], ...] = (
    {
        "id": "unit_declared",
        "description": "Every quantity view declares a physical unit.",
    },
    {
        "id": "color_scale_declared",
        "description": "Field images declare a colorbar and color-scale policy.",
    },
    {
        "id": "state_label_declared",
        "description": "Every view declares the time or parameter state it represents.",
    },
    {
        "id": "animation_frames_complete",
        "description": "Animation manifests declare expected frames and exported frames must be complete.",
    },
    {
        "id": "nonempty_image",
        "description": "Exported images must provide nonblank image metrics before acceptance.",
    },
)


def build_default_thermal_visualization_spec(
    thermal_spec: ThermalSimulationSpec,
    metrics: dict[str, Any] | None = None,
    source_work_order: dict[str, Any] | None = None,
) -> VisualizationSpec:
    metrics = metrics or {}
    state_label = _state_label(thermal_spec)
    return VisualizationSpec(
        source_request=thermal_spec.source_request,
        case_id=thermal_spec.template_id,
        study_type=thermal_spec.study_type,
        render_policy={
            "single_user_entry": True,
            "origin_scope": "1D/2D curves, parameter sweeps, and experiment comparisons.",
            "field_3d_scope": "3D temperature fields, slices, streamlines, and animations prefer COMSOL export or Python/PyVista/ParaView.",
            "placeholder_policy": "Write manifest and QA placeholders before real exporters are connected.",
        },
        global_color_scale={
            "quantity": "temperature",
            "unit": "degC",
            "policy": "global_across_temperature_views_when_comparing_cases",
            "suggested_min": _ambient_temperature(metrics, thermal_spec),
            "suggested_max": metrics.get("max_temperature_C"),
        },
        source_work_order=dict(source_work_order or {}),
        views=(
            VisualizationViewSpec(
                view_id="temperature_overview",
                title="Temperature Overview",
                role="field_context",
                output_kind="image",
                renderer="comsol_export_or_python_pyvista",
                view_type="3d_temperature_overview",
                quantity="temperature",
                unit="degC",
                state_label=state_label,
                required_annotations=(
                    "case_id",
                    "quantity_name",
                    "unit",
                    "colorbar",
                    "min_max_temperature",
                    "time_or_parameter_state",
                    "view_orientation",
                ),
                linked_metrics=("max_temperature_C", "temperature_rise_K"),
                linked_data=("temperature_field_export",),
            ),
            VisualizationViewSpec(
                view_id="key_slice",
                title="Key Slice",
                role="internal_hot_path_evidence",
                output_kind="image",
                renderer="comsol_export_or_python_pyvista",
                view_type="cut_plane_slice",
                quantity="temperature",
                unit="degC",
                state_label=state_label,
                required_annotations=(
                    "case_id",
                    "quantity_name",
                    "unit",
                    "colorbar",
                    "slice_plane",
                    "time_or_parameter_state",
                ),
                linked_metrics=("max_temperature_C",),
                linked_data=("slice_temperature_table",),
            ),
            VisualizationViewSpec(
                view_id="isotherm_threshold",
                title="Isotherm / Threshold View",
                role="engineering_limit_evidence",
                output_kind="image",
                renderer="comsol_export_or_python_pyvista",
                view_type="isotherm_or_threshold_surface",
                quantity="temperature_threshold",
                unit="degC",
                color_scale_policy="threshold_value_declared",
                state_label=state_label,
                required_annotations=(
                    "case_id",
                    "threshold_value",
                    "unit",
                    "colorbar",
                    "time_or_parameter_state",
                ),
                linked_metrics=("max_temperature_C",),
                linked_data=("threshold_region_export",),
                notes=("Use the user acceptance criterion when available; otherwise mark threshold as to_be_confirmed.",),
            ),
            VisualizationViewSpec(
                view_id="heat_flux_view",
                title="Heat Flux View",
                role="heat_flow_path_evidence",
                output_kind="image",
                renderer="comsol_export_or_python_pyvista_or_paraview",
                view_type="flux_magnitude_vector_or_streamline",
                quantity="heat_flux",
                unit="W/m^2",
                color_scale_policy="declared_heat_flux_scale",
                state_label=state_label,
                required_annotations=(
                    "case_id",
                    "quantity_name",
                    "unit",
                    "colorbar",
                    "vector_or_streamline_scale",
                    "time_or_parameter_state",
                ),
                linked_metrics=("energy_balance_error_percent",),
                linked_data=("heat_flux_field_export",),
            ),
            VisualizationViewSpec(
                view_id="probe_path_curves",
                title="Probe / Path Curves",
                role="quantitative_curve_evidence",
                output_kind="curve",
                renderer="origin",
                view_type="probe_or_path_temperature_curve",
                quantity="temperature",
                unit="degC",
                artifact_format="png",
                colorbar_required=False,
                color_scale_policy="not_applicable",
                state_label=state_label,
                required_annotations=(
                    "case_id",
                    "axis_labels",
                    "units",
                    "probe_or_path_id",
                    "time_or_parameter_state",
                ),
                linked_metrics=("max_temperature_C",),
                linked_data=("probe_table_csv", "path_profile_csv"),
                notes=("Origin owns this 1D/2D curve path; Python may provide a fallback table plot.",),
            ),
            VisualizationViewSpec(
                view_id="parameter_comparison",
                title="Parameter Comparison",
                role="sweep_or_experiment_comparison",
                output_kind="comparison",
                renderer="origin",
                view_type="parameter_sweep_or_experiment_comparison",
                quantity="temperature",
                unit="degC",
                artifact_format="png",
                colorbar_required=False,
                color_scale_policy="shared_axes_and_declared_series_scale",
                state_label="parameter_sweep/base_case",
                required_annotations=(
                    "case_id",
                    "axis_labels",
                    "units",
                    "parameter_labels",
                    "comparison_baseline",
                ),
                linked_metrics=("max_temperature_C", "temperature_rise_K"),
                linked_data=("parameter_sweep_table_csv", "experiment_comparison_csv"),
                notes=("Origin owns parameter-sweep curves and experiment overlays.",),
            ),
            VisualizationViewSpec(
                view_id="animation_manifest",
                title="Animation Manifest",
                role="transient_or_sweep_motion_evidence",
                output_kind="animation_manifest",
                renderer="comsol_export_or_python_pyvista_or_paraview",
                view_type="time_or_parameter_animation",
                quantity="temperature",
                unit="degC",
                artifact_format="json",
                color_scale_policy="fixed_camera_and_global_temperature_scale",
                state_label=_animation_state_label(thermal_spec),
                required_annotations=(
                    "case_id",
                    "quantity_name",
                    "unit",
                    "colorbar",
                    "frame_time_or_parameter_label",
                    "fixed_camera",
                ),
                linked_metrics=("max_temperature_C",),
                linked_data=("frame_sequence", "mp4_or_gif_export"),
                expected_frames=_default_expected_frames(thermal_spec),
                frame_rate_fps=_default_frame_rate(thermal_spec),
                notes=("Frame files are optional until a transient study or sweep result exists.",),
            ),
        ),
    )


def build_thermal_visualization_manifest(
    visualization_spec: VisualizationSpec,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for view in visualization_spec.views:
        entry = view.to_dict()
        entry["artifact"] = _artifact_stub(view, output_dir)
        entries.append(entry)

    return {
        "schema_version": "thermal-visualization-manifest/v1",
        "source_spec_schema_version": visualization_spec.schema_version,
        "case_id": visualization_spec.case_id,
        "study_type": visualization_spec.study_type,
        "status": "planned",
        "quality_rules": [dict(rule) for rule in THERMAL_VISUAL_QUALITY_RULES],
        "entries": entries,
    }


def evaluate_visualization_spec(visualization_spec: VisualizationSpec) -> list[CheckResult]:
    checks: list[CheckResult] = []
    view_ids = {view.view_id for view in visualization_spec.views}
    missing = [view_id for view_id in DEFAULT_THERMAL_VIEW_IDS if view_id not in view_ids]
    checks.append(
        CheckResult(
            name="thermal_visual_default_package",
            passed=not missing,
            message=(
                "Default thermal visualization package is declared."
                if not missing
                else f"Missing visualization views: {', '.join(missing)}."
            ),
        )
    )
    for view in visualization_spec.views:
        checks.extend(evaluate_visualization_view_metadata(view.to_dict()))
    return checks


def evaluate_visualization_manifest_quality(manifest: dict[str, Any]) -> list[CheckResult]:
    entries = [entry for entry in manifest.get("entries", []) if isinstance(entry, dict)]
    checks = [
        CheckResult(
            name="thermal_visual_manifest_schema",
            passed=manifest.get("schema_version") == "thermal-visualization-manifest/v1",
            message=(
                "Thermal visualization manifest schema is valid."
                if manifest.get("schema_version") == "thermal-visualization-manifest/v1"
                else "Thermal visualization manifest schema is missing or unsupported."
            ),
        ),
        CheckResult(
            name="thermal_visual_manifest_entries",
            passed=bool(entries),
            message=f"{len(entries)} visualization manifest entries declared.",
        ),
    ]
    for entry in entries:
        checks.extend(evaluate_visualization_view_metadata(entry))
        if entry.get("output_kind") == "animation_manifest":
            checks.extend(evaluate_animation_artifact_quality(entry))
        else:
            checks.extend(evaluate_visual_image_artifact_quality(entry))
    return checks


def evaluate_visualization_view_metadata(view: dict[str, Any]) -> list[CheckResult]:
    view_id = _view_id(view)
    annotations = {str(item) for item in view.get("required_annotations", []) if item is not None}
    needs_colorbar = bool(view.get("colorbar_required", False))
    checks = [
        CheckResult(
            name=f"thermal_visual_unit:{view_id}",
            passed=bool(view.get("unit")),
            message=(
                f"{view_id} declares unit {view.get('unit')}."
                if view.get("unit")
                else f"{view_id} is missing a physical unit."
            ),
        ),
        CheckResult(
            name=f"thermal_visual_color_scale:{view_id}",
            passed=bool(view.get("color_scale_policy")) and (not needs_colorbar or "colorbar" in annotations),
            message=(
                f"{view_id} declares color-scale policy {view.get('color_scale_policy')}."
                if bool(view.get("color_scale_policy")) and (not needs_colorbar or "colorbar" in annotations)
                else f"{view_id} is missing a color-scale policy or colorbar annotation."
            ),
        ),
        CheckResult(
            name=f"thermal_visual_state_label:{view_id}",
            passed=bool(view.get("state_label")),
            message=(
                f"{view_id} declares state label {view.get('state_label')}."
                if view.get("state_label")
                else f"{view_id} is missing a time or parameter label."
            ),
        ),
    ]
    return checks


def evaluate_visual_image_artifact_quality(view: dict[str, Any]) -> list[CheckResult]:
    view_id = _view_id(view)
    artifact = _artifact_metadata(view)
    if _is_planned_placeholder(view, artifact):
        return [
            CheckResult(
                name=f"thermal_visual_nonempty_image:{view_id}",
                passed=False,
                message=f"{view_id} image export is planned but not produced yet.",
                severity="warning",
            )
        ]

    metrics = _image_metrics(view, artifact)
    file_size = _number(artifact.get("file_size_bytes", view.get("file_size_bytes")), default=0.0)
    unique_colors = _number(metrics.get("unique_colors"), default=0.0)
    non_background_ratio = _number(metrics.get("non_background_ratio"), default=0.0)
    nonempty = file_size > 0 and unique_colors >= 2 and non_background_ratio > 0.0
    return [
        CheckResult(
            name=f"thermal_visual_nonempty_image:{view_id}",
            passed=nonempty,
            message=(
                f"{view_id} image metadata is nonblank: {int(unique_colors)} colors, "
                f"{non_background_ratio:.4f} non-background ratio."
                if nonempty
                else f"{view_id} image metadata is empty or missing nonblank metrics."
            ),
        )
    ]


def evaluate_animation_artifact_quality(animation: dict[str, Any]) -> list[CheckResult]:
    view_id = _view_id(animation)
    artifact = _artifact_metadata(animation)
    expected_frames = _int_or_zero(animation.get("expected_frames", artifact.get("expected_frames")))
    frames = _frames(animation, artifact)
    labels = _frame_labels(animation, frames)
    planned = _is_planned_placeholder(animation, artifact)
    severity = "warning" if planned else "error"

    checks = [
        CheckResult(
            name=f"thermal_animation_contract:{view_id}",
            passed=expected_frames >= 0 and bool(animation.get("color_scale_policy")),
            message=f"{view_id} declares expected_frames={expected_frames} and color-scale policy.",
        )
    ]
    if expected_frames == 0:
        checks.append(
            CheckResult(
                name=f"thermal_animation_frames_complete:{view_id}",
                passed=True,
                message=f"{view_id} does not require animation frames for this stationary/base manifest yet.",
                severity="warning",
            )
        )
        return checks

    complete = len(frames) == expected_frames
    labels_complete = len(labels) == expected_frames and all(label.strip() for label in labels)
    checks.extend(
        [
            CheckResult(
                name=f"thermal_animation_frames_complete:{view_id}",
                passed=complete,
                message=f"{view_id} has {len(frames)} of {expected_frames} expected frames.",
                severity=severity,
            ),
            CheckResult(
                name=f"thermal_animation_frame_labels:{view_id}",
                passed=labels_complete,
                message=f"{view_id} has {len(labels)} of {expected_frames} frame labels.",
                severity=severity,
            ),
        ]
    )
    return checks


def _artifact_stub(view: VisualizationViewSpec, output_dir: Path | None) -> dict[str, Any]:
    file_name = f"{view.view_id}.{view.artifact_format}"
    if view.view_id == "animation_manifest":
        file_name = "animation_manifest.json"
    path = Path("thermal_visualization") / file_name
    if output_dir is not None:
        path = output_dir / path
    return {
        "path": str(path),
        "format": view.artifact_format,
        "status": view.status,
        "placeholder": view.placeholder,
    }


def _state_label(thermal_spec: ThermalSimulationSpec) -> str:
    if "transient" in thermal_spec.study_type.lower() or "time" in thermal_spec.study_type.lower():
        return "time=to_be_exported"
    return "stationary/base_case"


def _animation_state_label(thermal_spec: ThermalSimulationSpec) -> str:
    if "transient" in thermal_spec.study_type.lower() or "time" in thermal_spec.study_type.lower():
        return "time_sequence"
    return "stationary_or_parameter_sweep_manifest"


def _default_expected_frames(thermal_spec: ThermalSimulationSpec) -> int:
    if "transient" in thermal_spec.study_type.lower() or "time" in thermal_spec.study_type.lower():
        return 30
    return 0


def _default_frame_rate(thermal_spec: ThermalSimulationSpec) -> float | None:
    if _default_expected_frames(thermal_spec) > 0:
        return 10.0
    return None


def _ambient_temperature(metrics: dict[str, Any], thermal_spec: ThermalSimulationSpec) -> float | None:
    if "ambient_temp_C" in metrics:
        return _number(metrics["ambient_temp_C"], default=0.0)
    for parameter in thermal_spec.parameters:
        if parameter.name == "ambient_temp_C":
            return parameter.value
    return None


def _artifact_metadata(view: dict[str, Any]) -> dict[str, Any]:
    artifact = view.get("artifact")
    if isinstance(artifact, dict):
        return artifact
    return {}


def _image_metrics(view: dict[str, Any], artifact: dict[str, Any]) -> dict[str, Any]:
    for candidate in (artifact.get("image_metrics"), view.get("image_metrics"), artifact.get("metrics"), view.get("metrics")):
        if isinstance(candidate, dict):
            return candidate
    return {}


def _frames(view: dict[str, Any], artifact: dict[str, Any]) -> list[dict[str, Any]]:
    raw = view.get("frames")
    if not raw:
        raw = artifact.get("frames")
    if not isinstance(raw, list):
        return []
    return [frame for frame in raw if isinstance(frame, dict)]


def _frame_labels(view: dict[str, Any], frames: list[dict[str, Any]]) -> list[str]:
    raw = view.get("frame_labels")
    if isinstance(raw, list) and raw:
        return [str(label) for label in raw]
    return [str(frame.get("label") or frame.get("state_label") or "") for frame in frames]


def _is_planned_placeholder(view: dict[str, Any], artifact: dict[str, Any]) -> bool:
    status = str(artifact.get("status", view.get("status", ""))).lower()
    placeholder = bool(artifact.get("placeholder", view.get("placeholder", False)))
    return placeholder or status in {"planned", "pending", "not_exported"}


def _view_id(view: dict[str, Any]) -> str:
    return str(view.get("view_id") or "unknown")


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

