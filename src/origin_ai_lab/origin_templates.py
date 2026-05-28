from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from origin_ai_lab.models import DatasetProfile, PlotKind, RouteDecision


@dataclass(frozen=True)
class OriginTaskTemplate:
    template_id: str
    label: str
    plot_kind: PlotKind
    default_fit_enabled: bool
    origin_features: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    non_goals: tuple[str, ...] = ()
    schema_version: str = "origin-task-template/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "template_id": self.template_id,
            "label": self.label,
            "plot_kind": self.plot_kind.value,
            "default_fit_enabled": self.default_fit_enabled,
            "origin_features": list(self.origin_features),
            "assumptions": list(self.assumptions),
            "non_goals": list(self.non_goals),
        }


GENERIC_XY = OriginTaskTemplate(
    template_id="generic_xy",
    label="Generic Origin XY plot",
    plot_kind=PlotKind.SCATTER,
    default_fit_enabled=True,
    origin_features=("worksheet import", "scatter/line graph", "optional linear fit", "figure export"),
    assumptions=("Use this when the request is a general XY plotting or calibration workflow.",),
)

TEMPLATES: dict[str, OriginTaskTemplate] = {
    "xrd": OriginTaskTemplate(
        template_id="xrd_pattern",
        label="XRD pattern plot in Origin",
        plot_kind=PlotKind.LINE,
        default_fit_enabled=False,
        origin_features=("line graph", "stacked/offset-ready spectrum", "peak markers", "reference overlay-ready"),
        assumptions=("Use Origin for plotting, normalization, peak marking, and reference overlays provided by the user.",),
        non_goals=("PDF database search/match", "Rietveld refinement", "phase identification"),
    ),
    "raman": OriginTaskTemplate(
        template_id="raman_spectrum",
        label="Raman spectrum plot in Origin",
        plot_kind=PlotKind.LINE,
        default_fit_enabled=False,
        origin_features=("line graph", "baseline/peak-analysis-ready spectrum", "peak markers"),
        assumptions=("Use Origin for plotting and local peak/baseline workflows, not spectral library identification.",),
        non_goals=("spectral database search", "chemical identity assignment"),
    ),
    "tga": OriginTaskTemplate(
        template_id="tga_curve",
        label="TGA curve plot in Origin",
        plot_kind=PlotKind.LINE,
        default_fit_enabled=False,
        origin_features=("line graph", "temperature curve", "derivative-column-ready worksheet"),
        assumptions=("Use Origin for thermal curve plotting and report export.",),
    ),
    "dsc": OriginTaskTemplate(
        template_id="dsc_curve",
        label="DSC curve plot in Origin",
        plot_kind=PlotKind.LINE,
        default_fit_enabled=False,
        origin_features=("line graph", "thermal baseline-ready curve", "area/integration-ready worksheet"),
        assumptions=("Use Origin for DSC curve plotting and local baseline/integration workflows.",),
    ),
    "battery": OriginTaskTemplate(
        template_id="battery_charge_discharge",
        label="Battery charge/discharge curve in Origin",
        plot_kind=PlotKind.LINE,
        default_fit_enabled=False,
        origin_features=("line graph", "multi-cycle-ready worksheet", "capacity-voltage plot"),
        assumptions=("Use Origin for plotting and comparing battery curves after instrument export.",),
    ),
    "eis": OriginTaskTemplate(
        template_id="eis_nyquist",
        label="EIS Nyquist plot in Origin",
        plot_kind=PlotKind.SCATTER,
        default_fit_enabled=False,
        origin_features=("scatter graph", "equal-axis-ready Nyquist plot", "multi-spectrum-ready worksheet"),
        assumptions=("Use Origin for Nyquist plotting and formatting after impedance data export.",),
        non_goals=("equivalent-circuit fitting",),
    ),
    "stress_strain": OriginTaskTemplate(
        template_id="stress_strain_curve",
        label="Stress-strain curve in Origin",
        plot_kind=PlotKind.LINE,
        default_fit_enabled=False,
        origin_features=("line graph", "mechanical curve", "modulus-fit-ready region selection"),
        assumptions=("Use Origin for curve plotting and selected-region fitting when explicitly requested.",),
    ),
    "particle_size": OriginTaskTemplate(
        template_id="particle_size_distribution",
        label="Particle-size distribution in Origin",
        plot_kind=PlotKind.HISTOGRAM,
        default_fit_enabled=False,
        origin_features=("histogram-ready data", "distribution plot", "summary-statistics-ready worksheet"),
        assumptions=("Use Origin for distribution plotting after measured diameters are exported.",),
    ),
}


def select_origin_template(
    route_decision: RouteDecision,
    profile: DatasetProfile,
    requested_plot_kind: PlotKind = PlotKind.AUTO,
) -> OriginTaskTemplate:
    if route_decision.instrument_family and route_decision.instrument_family in TEMPLATES:
        return TEMPLATES[route_decision.instrument_family]
    if requested_plot_kind == PlotKind.LINE:
        return OriginTaskTemplate(
            template_id="generic_xy_line",
            label="Generic Origin XY line plot",
            plot_kind=PlotKind.LINE,
            default_fit_enabled=True,
            origin_features=GENERIC_XY.origin_features,
            assumptions=GENERIC_XY.assumptions,
        )
    if len(profile.numeric_columns()) == 2:
        return GENERIC_XY
    return OriginTaskTemplate(
        template_id="generic_xy_confirm_columns",
        label="Generic Origin XY plot with column confirmation",
        plot_kind=PlotKind.SCATTER,
        default_fit_enabled=True,
        origin_features=GENERIC_XY.origin_features,
        assumptions=("Confirm x/y columns before running Origin.",),
    )
