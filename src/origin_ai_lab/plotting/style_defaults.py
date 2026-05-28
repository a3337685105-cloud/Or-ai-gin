from __future__ import annotations

from copy import deepcopy
from typing import Any

from origin_ai_lab.models import PlotKind, RouteDecision
from origin_ai_lab.origin_templates import OriginTaskTemplate


AXIS_TITLE_OVERRIDES = {
    "two_theta_deg": "2Theta (deg)",
    "intensity_counts": "Intensity (counts)",
    "raman_shift_cm-1": "Raman Shift (cm^-1)",
    "intensity_a.u.": "Intensity (a.u.)",
    "temperature_c": "Temperature (deg C)",
    "mass_percent": "Mass (%)",
    "derivative_percent_per_c": "Derivative Mass (%/deg C)",
    "heat_flow_mw": "Heat Flow (mW)",
    "capacity_mah_g": "Capacity (mAh/g)",
    "voltage_v": "Voltage (V)",
    "z_real_ohm": "Z' (Ohm)",
    "z_imag_neg_ohm": "-Z'' (Ohm)",
    "strain_percent": "Strain (%)",
    "strain": "Strain",
    "stress_mpa": "Stress (MPa)",
    "diameter_nm": "Diameter (nm)",
    "particle_size_nm": "Particle Size (nm)",
    "frequency_hz": "Frequency (Hz)",
    "current_ma": "Current (mA)",
    "potential_v": "Potential (V)",
    "time_s": "Time (s)",
    "signal_v": "Signal (V)",
}

TEMPLATE_TITLES = {
    "xrd_pattern": "XRD Pattern",
    "raman_spectrum": "Raman Spectrum",
    "tga_curve": "TGA Curve",
    "dsc_curve": "DSC Curve",
    "battery_charge_discharge": "Charge-Discharge Curve",
    "eis_nyquist": "Nyquist Plot",
    "stress_strain_curve": "Stress-Strain Curve",
    "particle_size_distribution": "Particle-Size Distribution",
}

SPECTRUM_TEMPLATES = {"xrd_pattern", "raman_spectrum"}
THERMAL_TEMPLATES = {"tga_curve", "dsc_curve"}


def default_axis_title(column: str | None) -> str:
    if not column:
        return ""
    normalized = _normalize_key(column)
    if normalized in AXIS_TITLE_OVERRIDES:
        return AXIS_TITLE_OVERRIDES[normalized]
    return _humanize_column_name(column)


def default_plot_title(
    x_column: str,
    y_column: str,
    origin_template: OriginTaskTemplate | None,
) -> str:
    if origin_template and origin_template.template_id in TEMPLATE_TITLES:
        return TEMPLATE_TITLES[origin_template.template_id]
    return f"{default_axis_title(y_column)} vs {default_axis_title(x_column)}"


def default_plot_style(
    plot_kind: PlotKind,
    origin_template: OriginTaskTemplate | None,
    route_decision: RouteDecision | None,
    user_style: dict[str, Any] | None = None,
    group_column: str | None = None,
    fit_enabled: bool = False,
) -> dict[str, Any]:
    template_id = origin_template.template_id if origin_template else ""
    style = _base_style(plot_kind, template_id, group_column=group_column, fit_enabled=fit_enabled)
    style["instrument_family"] = route_decision.instrument_family if route_decision else None
    return _deep_merge(style, user_style or {})


def _base_style(
    plot_kind: PlotKind,
    template_id: str,
    group_column: str | None,
    fit_enabled: bool,
) -> dict[str, Any]:
    is_line = plot_kind == PlotKind.LINE
    is_spectrum = template_id in SPECTRUM_TEMPLATES
    is_thermal = template_id in THERMAL_TEMPLATES

    if is_spectrum:
        series = {"color": "Black", "line_width": 2.2}
        peak_markers = {"color": "Red", "line_width": 1.2}
    elif is_thermal:
        series = {"color": "#1f77b4", "line_width": 2.2}
        peak_markers = {"color": "Red", "line_width": 1.0}
    elif is_line:
        series = {"color": "#1f77b4", "line_width": 2.0}
        peak_markers = {"color": "Red", "line_width": 1.0}
    else:
        series = {"color": "#1f77b4", "marker": "circle", "marker_size": 7, "line_width": 0.0}
        peak_markers = {"color": "Red", "line_width": 1.0}

    return {
        "theme": "origin-ai-clean-v1",
        "series": series,
        "fit_line": {"color": "Red", "line_width": 2.0},
        "peak_markers": peak_markers,
        "legend": {"show": bool(group_column or fit_enabled)},
        "export": {"width_px": 1600},
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _humanize_column_name(column: str) -> str:
    text = column.strip().replace("_", " ")
    replacements = {
        " deg": " (deg)",
        " c": " (deg C)",
        " v": " (V)",
        " mv": " (mV)",
        " ma": " (mA)",
        " hz": " (Hz)",
        " ohm": " (Ohm)",
        " percent": " (%)",
    }
    lower = text.lower()
    for suffix, unit in replacements.items():
        if lower.endswith(suffix):
            return text[: -len(suffix)].title() + unit
    return text.title()
