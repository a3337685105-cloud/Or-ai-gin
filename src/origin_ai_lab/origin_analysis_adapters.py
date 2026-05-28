from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from origin_ai_lab.models import PlotSpec, RouteDecision


@dataclass(frozen=True)
class OriginAnalysisAdapter:
    adapter_id: str
    label: str
    origin_capability: str
    status: str
    assumptions: tuple[str, ...] = ()
    non_goals: tuple[str, ...] = ()
    schema_version: str = "origin-analysis-adapter/v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "adapter_id": self.adapter_id,
            "label": self.label,
            "origin_capability": self.origin_capability,
            "status": self.status,
            "assumptions": list(self.assumptions),
            "non_goals": list(self.non_goals),
        }


def planned_origin_adapters(
    plot_spec: PlotSpec,
    route_decision: RouteDecision,
    peak_candidates: tuple[dict[str, float], ...] = (),
) -> tuple[OriginAnalysisAdapter, ...]:
    adapters: list[OriginAnalysisAdapter] = [
        OriginAnalysisAdapter(
            adapter_id="origin_graph_export",
            label="Origin graph/project export",
            origin_capability="originpro graph creation and export",
            status="implemented",
            assumptions=("Origin remains the final graph/project generator when use_origin is enabled.",),
        )
    ]
    if plot_spec.fit_enabled:
        adapters.append(
            OriginAnalysisAdapter(
                adapter_id="linear_fit_overlay",
                label="Linear fit overlay",
                origin_capability="Origin graph object overlay for a deterministic linear fit",
                status="implemented",
                assumptions=(
                    "The current adapter computes OLS deterministically in Python and renders the fit line in Origin.",
                    "A later adapter can swap this to Origin's native fitting report if needed.",
                ),
            )
        )
    if route_decision.instrument_family in {"xrd", "raman"} and peak_candidates:
        adapters.append(
            OriginAnalysisAdapter(
                adapter_id="spectrum_peak_markers",
                label="Spectrum peak markers",
                origin_capability="Origin line/annotation objects for peak markers",
                status="implemented",
                assumptions=("Peak candidates are detected deterministically, then rendered as Origin graph objects.",),
                non_goals=("phase identification", "spectral library search", "database-backed matching"),
            )
        )
    if route_decision.instrument_family == "dsc":
        adapters.append(
            OriginAnalysisAdapter(
                adapter_id="dsc_baseline_future",
                label="DSC baseline/integration adapter",
                origin_capability="Origin baseline/integration workflow",
                status="planned",
                assumptions=("Use only after a local Origin workflow is wrapped and validated with a golden dataset.",),
            )
        )
    return tuple(adapters)
