# Research Intake Case Study Findings

## Purpose

This note records the case-study basis for the "read thick, then read thin" intake harness.
The product should not ask users to fill a COMSOL-style form. It should gather rich context,
preserve it, and compress it into a work order only after the user's research intent is clear.

## Cross-Case Pattern

Across COMSOL, Ansys, V&V, and DOE examples, valuable simulation results usually start from
the same input dimensions:

| Dimension | What We Need To Capture |
| --- | --- |
| Decision/use | Internal direction check, experiment planning, presentation, paper figure, external validation. |
| Real system | What object or process is being modeled, and what boundary is included/excluded. |
| Geometry | CAD/ECAD/MPH, dimensions, simplified primitives, symmetry, thin layers, contact gaps. |
| Materials | Thermal conductivity, density, heat capacity, emissivity, electrical properties, TIM/contact data. |
| Heat/load source | Total power, heat flux, volumetric heat, Joule heating, battery heat, transient profile. |
| Cooling/boundary | Natural/forced convection, liquid cooling, fixed temperature, insulation, radiation, inlet/outlet. |
| Physics choice | Conduction, conjugate heat transfer, radiation, Joule heating, thermal contact, transient thermal. |
| Quantities of interest | Tmax, hotspot, probe temperature, heat flux, thermal resistance, pressure drop, time response. |
| Constraints | Temperature limit, uniformity, pressure drop, size/cost/weight, safety, publication standard. |
| Validation data | Experiment CSV, thermocouples, IR images, analytical solution, benchmark, prior runs. |
| Output need | Short memo, experiment plan, temperature images, animation, report, paper methods/figure. |

## Case-Derived Prompts

The assistant should start with plain research language:

- What are you trying to decide or prove?
- What would make the scheme fail?
- What do you already know about the object, dimensions, materials, heat source, and cooling path?
- Do you need a quick internal answer or a result others will inspect?
- Do you have any experiment, reference, or expected trend to check against?

Then it should ask domain-specific questions only when needed:

- Is this mostly pure conduction, electronics cooling, wind/liquid cooling, Joule heating, thermal contact, or a local heat-source problem?
- Is the heat source a total power, heat flux, volumetric heat, voltage/current loss, or measured loss profile?
- Is there a contact layer, air gap, thermal paste, thin copper layer, or rough interface?
- Should we compare variants or scan key parameters?

## Thick-To-Thin Data Flow

The intake harness should store three layers:

1. `thick_context`: all user-provided fragments, files, notes, examples, motivations, and assumptions.
2. `core_thread`: the compressed execution thread: goal, job, system, QoI, criterion, planned output.
3. `evidence_trace`: where each important claim came from: user, file, literature, experiment, script, or default.

This avoids two bad outcomes:

- asking the user to complete a long expert form before the assistant can help;
- losing context by summarizing too aggressively too early.

## Initial Implementation

`src/origin_ai_lab/agents/research_intake_harness.py` now implements:

- the guided thermal intake question bank;
- `ResearchWorkOrder`;
- thick-context capture;
- thin work-order compression;
- blocking-question selection.

CLI smoke:

```powershell
python -m origin_ai_lab.cli research-intake "我想判断5W芯片贴在铝板上会不会超过80度，先给我自己判断方向用"
python -m origin_ai_lab.cli research-intake --question-bank
```

## Sources

COMSOL case sources:

- Electronic Chip Cooling: https://doc.comsol.com/5.6/doc/com.comsol.help.models.heat.chip_cooling/chip_cooling.html
- Thin Plate: https://doc.comsol.com/6.4/doc/com.comsol.help.models.heat.thin_plate/thin_plate.html
- Heat Conduction in a Finite Slab: https://doc.comsol.com/5.4/doc/com.comsol.help.models.heat.heat_conduction_in_slab/heat_conduction_in_slab.html
- Localized Heat Source: https://doc.comsol.com/6.3/doc/com.comsol.help.models.heat.localized_heat_source/localized_heat_source.html
- Surface-Mount Package: https://doc.comsol.com/6.3/doc/com.comsol.help.models.heat.surface_mount_package/surface_mount_package.html
- Thermal Contact Package Heat Sink: https://doc.comsol.com/5.4/doc/com.comsol.help.models.heat.thermal_contact_electronic_package_heat_sink/thermal_contact_electronic_package_heat_sink.html

Ansys and engineering sources:

- Ansys Icepak: https://www.ansys.com/en-gb/products/electronics/ansys-icepak
- Electronics Thermal Management: https://www.ansys.com/en-gb/simulation-topics/what-is-electronics-thermal-management
- Fluent heat sink example: https://innovationspace.ansys.com/courses/courses/intro-to-heat-transfer-in-fluids/lessons/simulation-examples-homeworks-and-quiz/topic/cooling-a-heat-sink-with-convective-heat-transfer-simulation-example/
- PyFluent CHT example: https://examples.fluent.docs.pyansys.com/version/dev/examples/00-released_examples/03-CHT.html
- Ansys Battery Modeling: https://www.ansys.com/applications/battery

V&V and DOE sources:

- NASA-STD-7009B: https://standards.nasa.gov/standard/nasa/nasa-std-7009
- ASME V&V 40 overview: https://www.asme.org/codes-standards/find-codes-standards/assessing-credibility-of-computational-modeling-through-verification-and-validation-application-to-medical-devices
- ASME VVUQ standards overview: https://www.asme.org/about-asme/standards/verification-validation-uncertainty
- NIST DOE objectives: https://www.itl.nist.gov/div898/handbook/pri/section3/pri31.htm
- NIST DOE steps: https://www.itl.nist.gov/div898/handbook/pri/section1/pri14.htm

