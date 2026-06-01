# Research Assistant Product Design

## Product North Star

The product should feel like a scientific research assistant, not a thinner wrapper around
COMSOL, Origin, or any other expert tool.

The user should not choose from many technical entry points. They should start from one place:

```text
"Tell me what you want to understand, prove, compare, or show."
```

The system then turns that intent into a structured research work order, asks only blocking
questions, runs the right tools, and returns results in the form the user actually needs.

## Primary User Jobs

### 1. Think For Themselves

Researchers want to decide whether an experimental direction is worth trying.

Typical intent:

- "Will this heat dissipation scheme probably work?"
- "Before I machine this part, can we estimate whether the temperature will exceed 80 C?"
- "Which factor matters more: material thermal conductivity, contact resistance, or airflow?"

Expected output:

- Feasibility memo.
- Key assumptions.
- Fast approximate simulation or template-based COMSOL run.
- Sensitivity ranking.
- Risk and next-experiment suggestions.

### 2. Plan An Experiment

Researchers want to reduce trial-and-error before doing real lab work.

Typical intent:

- "Help me design a thermal experiment to compare these two packages."
- "Where should I place thermocouples?"
- "What power range should I test?"

Expected output:

- Experiment plan.
- Parameter matrix.
- Sensor/probe placement suggestion.
- Expected curves or temperature ranges.
- Failure modes to watch.

### 3. Explain And Present A Scheme

Researchers need to convince collaborators, supervisors, reviewers, or funders.

Typical intent:

- "Make figures to explain why this cooling design is better."
- "Generate a report comparing方案A and方案B."
- "I need a clean image showing the hot spot and heat-flow path."

Expected output:

- Comparison report.
- Temperature-field figures.
- Heat-flow/slice/probe visual package.
- Key tables and talking points.
- Exportable images and animations.

### 4. Prepare Paper-Quality Evidence

Researchers need reproducible, publication-ready figures and supporting material.

Typical intent:

- "Make a paper figure for the temperature distribution."
- "Export a parameter sweep figure and describe the simulation setup."
- "Generate supplementary-methods text from the simulation."

Expected output:

- High-resolution figure set.
- Plot data CSV.
- Methods paragraph.
- Model/mesh/solver summary.
- Validation and limitation notes.

## One User-Facing Input Flow

There should be one front door in the UI:

```text
Goal + optional files + desired output
```

The user can provide any subset of:

| Input | Examples | Required? |
| --- | --- | --- |
| Natural-language goal | "Estimate whether this chip overheats at 5 W." | Always |
| Desired output | "给我自己判断用", "做汇报图", "论文插图", "实验方案" | Optional |
| Geometry description | "50 mm aluminum plate with 10 mm chip on top" | Optional |
| Existing files | CAD, COMSOL MPH, CSV, Excel, images, sketches, Origin project | Optional |
| Materials | Aluminum, copper, silicon, user material table | Optional |
| Heat/load conditions | Power, ambient temperature, convection coefficient, airflow | Optional |
| Constraints | Max temperature, size limit, material limit, target journal style | Optional |
| Evidence level | quick estimate, design comparison, publication-quality, validation report | Optional |

If information is missing, the system should ask the smallest possible blocking question:

- "Do you want a quick estimate or a COMSOL-quality simulation?"
- "What is the heat source power?"
- "Do you have a geometry file, or should I use a simplified block model?"
- "Is this for internal decision-making or paper/presentation output?"

Non-blocking gaps should become assumptions, not long forms.

## Thick-To-Thin Intake

The intake flow should behave like "read the book thick, then read it thin."

First, the system should collect and preserve as much user context as possible. A researcher
often carries the real problem as fragments: lab motivation, a half-known geometry, a power
number from a datasheet, a rough mental picture of airflow, a target figure for a paper, a
warning from a previous failed experiment. The product should not throw these details away just
because they are not yet COMSOL-ready.

Then the system compresses the thick context into a thin execution thread:

```text
raw goal
-> user job
-> real-world system and boundary
-> key inputs and assumptions
-> quantity of interest
-> decision criterion
-> minimum credible method
-> planned outputs
-> blocking questions
```

The thick layer remains as trace. The thin layer drives tools.

### Guided Question Bank

The first version of the question bank is implemented in
`src/origin_ai_lab/agents/research_intake_harness.py`.

The user should not see all questions at once. The assistant chooses the next 1-3 blocking
questions based on what is missing.

Core dimensions:

| Dimension | Why It Matters |
| --- | --- |
| Intended use | Internal判断、实验方案、展示、论文图、验证报告 need different rigor. |
| System description | Preserves the user's real research context before software terms distort it. |
| Geometry | Chooses CAD, existing MPH, or simplified primitives. |
| Materials | Thermal conductivity, density, heat capacity, emissivity, contact materials. |
| Heat sources | Power, heat flux, volumetric heating, source size, source location, time dependence. |
| Cooling boundaries | Convection, fixed temperature, insulation, radiation, inlet/outlet flow. |
| Quantities of interest | Max temperature, hot spot, heat flux path, probe temperature, time response. |
| Constraints | Temperature limit, uniformity, pressure drop, size, cost, paper/presentation needs. |
| Comparison or sweep | Turns single runs into design decisions and sensitivity insight. |
| Validation data | Upgrades a plausible result into evidence. |
| Output format | Memo, experiment plan, figures, animation, report, paper methods text. |

### Case-Derived Intake Harness

The question bank comes from real heat simulation cases, not imagined forms:

- COMSOL chip cooling: geometry, chip power, heat sink, thermal contact, airflow, radiation,
  max chip temperature, velocity field, temperature field.
- COMSOL thin plate: dimensions, material, fixed-temperature boundary, convection/radiation,
  2D vs 3D validation curve.
- COMSOL localized heat source: disk radius, heat-source radius/power, fixed boundary
  temperature, analytical comparison, mesh-size effect.
- COMSOL surface-mount package: PCB/package/chip geometry, materials, nearby voltage regulator,
  convection, chip max temperature and cut-plane views.
- COMSOL thermal contact package: contact pressure, microhardness, roughness, airflow, contact
  conductance, parameter sweep.
- Ansys electronics cooling and battery cases: ECAD/MCAD, power maps, airflow/liquid cooling,
  pressure drop, drive cycles, experimental data, ROM/high-fidelity validation.

This means the assistant asks practical questions like:

- "What failure risk are you trying to avoid: over-temperature, nonuniformity, pressure drop,
  thermal runaway, or unclear mechanism?"
- "Do you have CAD/ECAD/MPH, or should I start with simplified geometry?"
- "Is the heat source total power, heat flux, voltage/current, or measured loss data?"
- "What cooling path exists: natural convection, forced air, liquid, fixed-temperature surface,
  radiation, or contact into another part?"
- "Do you need a quick internal answer or a figure/report that others will inspect?"

## Internal Work Order

Every request should become one internal work order:

```json
{
  "goal": "Estimate whether a 5 W chip on an aluminum plate exceeds 80 C.",
  "user_job": "feasibility",
  "evidence_level": "quick_screening",
  "available_inputs": ["natural_language"],
  "missing_blockers": [],
  "assumptions": [
    "Use simplified block geometry.",
    "Use natural convection h=10 W/(m^2*K)."
  ],
  "planned_outputs": [
    "temperature_estimate",
    "risk_summary",
    "next_experiment_suggestions"
  ]
}
```

This work order is the stable center of the product. Tools change underneath it; the user flow
does not.

## Output Ladder

The system should scale output by user intent, not by exposing separate product entrances.

| User Need | Output Package | Internal Capabilities |
| --- | --- | --- |
| Quick self-check | Short memo, rough temperature/risk, assumptions | Rule/LLM intake, simplified physics, mock/template run |
| Experiment planning | Parameter matrix, sensor placement, expected ranges | Sensitivity planning, probe suggestions, report draft |
| Design comparison | A/B plots, temperature fields, sweep table, conclusion | COMSOL template runs, data export, Origin plots |
| Presentation | Clean images, animations, annotated story | COMSOL/Python visualization, figure QA, export manifest |
| Paper figure | High-res images, plot data, methods text, limitations | Reproducibility manifest, validation checks, citation-ready report |
| Validation package | Mesh convergence, energy balance, benchmark/experiment comparison | V&V harness, golden cases, error metrics |

The same request box can produce any of these. The system asks for the intended use only when
it changes the required rigor or artifact format.

## Role Of The LLM

The LLM should be present from the beginning as the intent and orchestration layer:

- Understand the research goal.
- Identify the user job.
- Translate messy language into a work order.
- Propose assumptions.
- Choose the next tool path: quick estimate, template simulation, visualization, report, or validation.
- Explain results in the user's scientific context.

The safety boundary is not "LLM later"; it is:

```text
LLM proposes, tools execute, validators judge, user can inspect.
```

The LLM should not directly execute arbitrary COMSOL/Origin code. It should generate structured
plans and model proposals that pass harness validation before execution.

## UI Principle

The frontend should not expose:

- "COMSOL mode"
- "Origin mode"
- "V&V mode"
- "Animation mode"
- "Report mode"

It should expose:

- A command box.
- File/context upload.
- A compact "AI understood this as..." card.
- A small set of editable core slots.
- A result workspace with tabs for Summary, Model, Results, Figures, Validation, Files.

Tabs are result organization, not separate entrances.

## Capability Direction

The next engineering work should be organized around user-facing jobs:

1. `research_intake`: turn a natural-language goal into a work order.
2. `evidence_router`: decide the minimum credible path for the requested output.
3. `simulation_runner`: run quick estimates or COMSOL templates.
4. `visual_package`: produce figures, animations, and data exports.
5. `report_builder`: assemble a result package with assumptions and missing evidence.
6. `validation_harness`: upgrade evidence when the user needs publication or external claims.

This keeps the product as a central assistant while allowing the backend to grow in rigor.
