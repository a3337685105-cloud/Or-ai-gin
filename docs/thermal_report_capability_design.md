# Thermal Simulation Report Capability Design

## Why This Exists

Thermal simulation results are only useful when they are inspectable, reproducible, and tied
to explicit engineering decisions. A convincing report is not a gallery of attractive plots.
It is an evidence package:

```text
model intent
-> assumptions and inputs
-> geometry/materials/physics/mesh/solver
-> convergence and V&V checks
-> visual field evidence
-> curves/tables for quantitative claims
-> limitations, risks, and reproducible artifacts
```

This document converts the research findings into capabilities for Origin AI Lab's
COMSOL/thermal simulation track.

## High-Quality Report Structure

| Section | Required Evidence |
| --- | --- |
| Summary and decision | Main conclusion, pass/fail against target, top risks, applicability boundary. |
| Objective and acceptance criteria | Context of use, quantities of interest, allowed error, temperature limits, safety margin. |
| Model description | Geometry, materials, heat sources, boundary conditions, coupling assumptions, study type. |
| Input provenance | Material/source table, power assumptions, ambient conditions, contact resistance, units. |
| Geometry and selections | Images or tables showing domains, boundaries, heat-source regions, probe locations. |
| Mesh and discretization | Mesh statistics, element quality, refined regions, mesh/time-step independence status. |
| Solver and convergence | Solver settings, residual/convergence log summary, warnings, failed iterations. |
| Results evidence package | Temperature field, slices, isotherms, heat flux, probes, profiles, parameter comparisons. |
| V&V and credibility | Golden case result, energy balance, experiment/benchmark comparison, uncertainty notes. |
| Limitations and next actions | Unverified assumptions, model simplifications, required experiments or refinements. |
| Reproducibility appendix | Software versions, command line, model file, logs, exported tables, images, animations, hashes. |

## Visualization Package

A thermal run should produce a visualization manifest, not isolated figures.

Minimum static outputs:

- Temperature overview surface/cloud plot with units, colorbar, min/max, time or parameter label.
- Key slice or cut-plane through the suspected hot path.
- Isotherm or threshold-temperature view for engineering limits.
- Heat-flux magnitude and/or heat-flux vector/streamline view.
- Geometry/boundary-condition overview showing heat sources, convection/fixed-temperature surfaces, probes.
- Probe or path curves for quantitative inspection.
- Parameter-sweep comparison using consistent color scale, camera, units, and range.

Animation outputs when the model is transient or parameterized:

- Time animation for transient thermal diffusion or cooling.
- Parameter sweep animation for power, convection coefficient, flow rate, or material changes.
- Image sequence plus MP4/GIF, so individual frames can be audited.

Quality rules:

- Every figure needs quantity name, unit, colorbar, case id, time/parameter state, and viewpoint context.
- Comparison images must use a shared or explicitly declared color scale.
- Animations should normally fix camera and global color scale.
- A visual result cannot be accepted without linked numeric metrics and raw export data.
- 3D field plots should be accompanied by slice/probe/profile plots so internal hot spots are not hidden.

## Validation And Credibility Checks

| Check | Required Capability |
| --- | --- |
| Environment reproducibility | `origin-ai doctor`, solver version capture, OS/hardware/log capture. |
| Input/unit preflight | Unit-aware parameter schema, range checks, missing-source warnings. |
| Boundary-condition audit | Export BC table with type, target, value, unit, source, and reviewed status. |
| Solver log parsing | Detect convergence, warnings, residual trends, failed nonlinear steps, run time. |
| Mesh/time-step independence | Run coarse/medium/fine sweeps, extract QoI, plot convergence, compute relative change or GCI. |
| Energy balance | Integrate heat input, boundary flux, storage terms, and report imbalance. |
| Golden case regression | Maintain official COMSOL/benchmark cases with expected outcomes and tolerances. |
| Experiment comparison | Import measurement CSV, align probes/path/time, plot error with uncertainty bands. |
| Sensitivity/UQ | Parameter sweeps or DOE for material, convection, contact, power, ambient conditions. |
| Evidence manifest | Persist every input, command, artifact, hash, plot spec, and report section status. |

## Capability Roadmap

### Level 0: Current Foundation

- Discover Origin and COMSOL installs.
- Run official COMSOL `.mph` templates through `comsolbatch`.
- Generate `thermal_simulation_spec.json`, execution plan, solver log, solved `.mph`, and result JSON.
- Maintain official thermal case registry and dry-run harness.

### Level 1: Report Skeleton And Evidence Manifest

- Add `thermal_report_manifest.json` with sections, required evidence, and completeness status.
- Generate an initial Markdown/HTML report from existing artifacts.
- Include solver version, command line, model path, log summary, and acceptance criteria.
- Mark missing evidence explicitly instead of hiding gaps.

### Level 2: COMSOL Result Export

- Export temperature images, selected plot groups, and data tables from COMSOL.
- Extract max/min temperature, probe values, path curves, and heat flux summaries.
- Save image/data specs so report figures are reproducible.
- Reuse Origin for 1D/2D curves and parameter comparison plots.

### Level 3: Visualization Package

- Generate default thermal visualization set: overview, slices, isotherms, heat flux, probes, parameter comparisons.
- Support animation manifest: frame count, fps, color-scale policy, time/parameter labels, output formats.
- Add visual QA checks: colorbar/unit presence, frame completeness, nonblank images, consistent scale.
- Current scaffold writes `thermal_visualization_spec.json`, `thermal_visualization_manifest.json`, and `thermal_visualization_quality.json`
  from the thermal workflow. The manifest is a planned evidence package until COMSOL/Python/Origin exporters attach real images,
  curves, frame sequences, and image metrics.
- `thermal-visualization-spec/v1` keeps 3D field views on COMSOL/Python/PyVista/ParaView paths while reserving Origin for
  probe/path curves, parameter sweeps, and experiment comparisons.

### Level 4: V&V Harness

- Add golden-case comparators for `busbar_smoke`, `thin_plate_verification`, `chip_cooling_reference`, and conduction tutorials.
- Add mesh/time-step sweep runner and convergence plots.
- Add energy-balance and boundary-condition audit.
- Add sensitivity runner for common thermal parameters.

### Level 5: LLM-Assisted Modeling

- Accept only constrained `thermal-model-proposal/v1` JSON from the LLM.
- Validate geometry primitives, dimensions, materials, assignments, heat sources, BCs, and observables.
- Generate COMSOL Java/MATLAB methods only after schema validation.
- Keep human approval for new geometry/topology and unreviewed physics.

## Project Implications

Origin AI Lab should treat images and animations as evidence artifacts linked to numeric
checks, not decorative assets. The report generator should show both what is known and what is
missing. A strong AI simulation assistant is therefore less like a one-shot prompt-to-model
tool and more like a lab notebook that can operate COMSOL, Origin, and validation scripts
without losing the chain of custody.

## Sources

- COMSOL model reports and result export: https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_ref_results.37.221.html
- COMSOL plot groups and plot types: https://doc.comsol.com/6.3/doc/com.comsol.help.comsol/comsol_ref_results.37.102.html
- COMSOL animation export: https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_ref_results.37.223.html
- COMSOL high-quality visualization guidance: https://www.comsol.com/support/learning-center/article/101922
- COMSOL mesh refinement study: https://www.comsol.com/support/knowledgebase/1261
- Ansys Fluent simulation reports: https://ansyshelp.ansys.com/public/Views/Secured/corp/v242/en/flu_ug/flu_ug_chp_simulation_reports_view.html
- NASA-STD-7009B models and simulations: https://standards.nasa.gov/node/263
- NASA grid convergence / GCI tutorial: https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html
- ASME V&V 20 for CFD and heat transfer: https://www.asme.org/codes-standards/find-codes-standards/standard-for-verification-and-validation-in-computational-fluid-dynamics-and-heat-transfer/2009/pdf/
- NAFEMS verification and validation overview: https://www.nafems.org/publications/resource_center/wt09/

