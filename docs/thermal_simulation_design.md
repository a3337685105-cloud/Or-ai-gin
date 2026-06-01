# Thermal Simulation Scaffold

## Positioning

This is the first scaffold for adding COMSOL-style thermal simulation to Origin AI Lab.
It deliberately mirrors the existing Origin boundary:

```text
natural-language request
-> structured thermal spec
-> guarded execution plan
-> deterministic solver connector
-> result artifacts and audit log
```

The current implementation does not require COMSOL. It supports:

- `mock`: runs a deterministic lumped thermal-resistance calculation.
- `dry-run`: writes the plan and spec without solving.
- `comsol`: runs a validated `.mph` template through COMSOL's batch executable and records the solver log and solved model.

## Developer Command

```powershell
origin-ai thermal --backend mock --out runs/thermal_demo `
  --param chip_power_W=5 `
  --param ambient_temp_C=25 `
  --param h_conv_W_m2K=10
```

Equivalent module entry point:

```powershell
python -m origin_ai_lab.cli thermal --backend mock --out runs/thermal_demo --param chip_power_W=5
```

Environment discovery:

```powershell
origin-ai doctor
```

COMSOL batch smoke test with an official Application Library model:

```powershell
python -m origin_ai_lab.cli thermal --backend comsol --case busbar_smoke --out runs\thermal_comsol_busbar
```

Harness dry-run with selected official cases:

```powershell
python -m origin_ai_lab.cli thermal-harness --backend dry-run --case busbar_smoke --case chip_cooling_reference
```

## Generated Artifacts

- `thermal_simulation_spec.json`: stable task contract for the thermal run.
- `thermal_execution_plan.json`: tool steps and guardrails.
- `thermal_summary.csv`: mock backend metrics for plotting/reporting.
- `thermal_result.json`: checks, metrics, artifact paths, and pass/fail status.
- `*_solved.mph`: COMSOL backend solved model output.
- `*_comsolbatch.log`: COMSOL batch solver log.

## Initial Thermal Parameters

| Parameter | Unit | Purpose |
| --- | --- | --- |
| `chip_power_W` | W | Heat-source power. |
| `ambient_temp_C` | degC | Ambient boundary temperature. |
| `h_conv_W_m2K` | W/(m^2*K) | Convection coefficient. |
| `cooling_area_m2` | m^2 | Effective exposed cooling area for the mock model. |
| `base_resistance_K_W` | K/W | Lumped conduction/contact resistance for the mock model. |

The mock model is only a reproducibility scaffold. It must not be treated as a validated physical COMSOL result.

## How Geometry Is Built

The current COMSOL connector is template-first: it loads an existing `.mph` file, runs a named
study, and saves a solved model. That means the actual geometry in the current smoke test is
already inside the official COMSOL model file. We are not yet programmatically inserting
blocks, spheres, cylinders, materials, or boundary selections into a blank model.

There are three safe levels of model creation:

1. Template parameterization: an expert builds a `.mph` template in COMSOL, names the
   parameters and selections, and the AI only changes reviewed values.
2. Template method calls: an expert adds COMSOL methods that create or update specific
   geometry features. The AI calls only approved methods.
3. Generated geometry code: the AI proposes a constrained JSON model, the harness validates
   it, and a code generator emits COMSOL Java/MATLAB API calls.

COMSOL's Java/MATLAB APIs create primitives through geometry features. Conceptually:

```java
model.geom("geom1").create("blk1", "Block");
model.geom("geom1").feature("blk1").set("size", new String[]{"0.05", "0.05", "0.003"});
model.geom("geom1").feature("blk1").set("pos", new String[]{"0", "0", "0"});

model.geom("geom1").create("sph1", "Sphere");
model.geom("geom1").feature("sph1").set("r", "0.002");
model.geom("geom1").feature("sph1").set("pos", new String[]{"0", "0", "0.002"});
```

The harness intentionally puts a JSON contract in front of that API so the LLM never gets to
emit arbitrary model-building code as the first executable artifact.

## LLM Modeling Harness

The thermal harness writes a schema, an example proposal, a validation report, and an official
case inventory:

```powershell
python -m origin_ai_lab.cli thermal-harness --backend dry-run --out runs\thermal_harness
```

The constrained LLM proposal format is:

```json
{
  "schema_version": "thermal-model-proposal/v1",
  "geometry": [
    {"id": "plate", "type": "block", "size_m": [0.05, 0.05, 0.003], "center_m": [0, 0, 0]},
    {"id": "probe", "type": "sphere", "radius_m": 0.001, "center_m": [0.015, 0, 0.003]}
  ],
  "materials": [{"id": "aluminum", "thermal_conductivity_W_mK": 205}],
  "assignments": [{"geometry_id": "plate", "material_id": "aluminum"}],
  "heat_sources": [{"id": "chip_heat", "type": "total_power", "target": "plate", "value_W": 5}],
  "boundary_conditions": [{"id": "ambient", "type": "convection", "target": "all_exterior_surfaces", "h_W_m2K": 10, "ambient_temp_C": 25}],
  "observables": ["max_temperature_C", "energy_balance"]
}
```

Harness validation currently checks:

- geometry primitives are from the allowed set: block, sphere, cylinder;
- dimensions and radii are positive and in SI meters;
- every primitive has a material assignment;
- material thermal conductivity is declared;
- at least one heat source exists and targets a known domain;
- at least one heat sink/reference exists, such as convection or fixed temperature;
- requested observables are explicit.

This gives the LLM a useful modeling surface while keeping the executable boundary inspectable.

## COMSOL Connection Plan

`ComsolThermalClient` currently uses COMSOL's documented batch interface:

```text
comsolbatch -inputfile in.mph -outputfile out.mph -study std1
```

This is enough to validate local COMSOL installation, license availability, model loading,
solver execution, and output-file generation. Parameter mutation is intentionally not enabled
yet for arbitrary models. COMSOL supports command-line parameter injection through `-pname`,
`-plist`, and `-paramfile`, and LiveLink for MATLAB can modify parameters with `mphsetparam`.
Those paths should be added only after a template exposes reviewed parameter names.

Recommended first smoke test:

1. Build or obtain a small stationary heat-transfer `.mph` template.
2. Confirm that the template exposes named parameters matching the thermal spec.
3. Run a script outside this repo to open the template, set parameters, solve, and export a CSV.
4. Move only the stable script boundary into `ComsolThermalClient`.
5. Add checks for solver convergence, max temperature, exported table existence, and energy-balance sanity.

The AI layer should continue to edit only the white-listed parameter fields. It should not create arbitrary physics, geometry, mesh, or solver settings without a reviewed template.

## Current Local Smoke Result

On 2026-06-01, the project successfully detected and ran:

- COMSOL Multiphysics 6.4.0.293
- `comsolbatch.exe` at `C:\Program Files\COMSOL\COMSOL64\Multiphysics\bin\win64\comsolbatch.exe`
- Official model: `COMSOL_Multiphysics\Multiphysics\busbar.mph`
- Study tag: `std1`
- Output: `runs\thermal_comsol_busbar\busbar_solved.mph`
- Log: `runs\thermal_comsol_busbar\busbar_comsolbatch.log`

The solver log reached 100% completion and saved the solved MPH file. This proves the first
connector boundary works. It does not yet prove that AI-selected parameters are applied or that
thermal metrics are extracted from the solved model.

## Official Test Objects and Acceptance Standards

Use official COMSOL examples before custom lab models. They give us stable objects, documented
paths, and expected qualitative or numeric outcomes.

| Stage | Model | Local library path | Purpose | Initial acceptance standard |
| --- | --- | --- | --- | --- |
| 0 | Electrical Heating in a Busbar | `COMSOL_Multiphysics\Multiphysics\busbar.mph` | Check COMSOL install, license, batch execution, and study tag handling. | `comsolbatch` exits 0, log reaches 100%, solved MPH exists, no error lines in log. |
| 1 | Out-of-Plane Heat Transfer for a Thin Plate | `Heat_Transfer_Module\Verification_Examples\thin_plate.mph` | Verification-style heat-transfer case with 2D/3D comparison. | Batch run succeeds; exported comparison data later shows 2D and 3D temperature profiles close to the documented overlap. |
| 2 | Electronic Chip Cooling | `Heat_Transfer_Module\Tutorials,_Forced_and_Natural_Convection\chip_cooling.mph` | Domain-relevant electronics cooling case. | For documented configurations, max chip temperature should be near the published values: ideal contact about 84 degC, air-layer case close to 95 degC, nonisothermal-flow case about 90 degC, radiation case about 80 degC. |
| 3 | Heat Conduction in a Slab | `Heat_Transfer_Module\Tutorials,_Conduction\heat_conduction_in_slab.mph` | Basic conduction tutorial for slab temperature profiles. | Batch run succeeds; later exported profiles follow the documented conduction trend. |
| 4 | Cylinder Conduction | `Heat_Transfer_Module\Tutorials,_Conduction\cylinder_conduction.mph` | Radial/cylindrical conduction coverage. | Batch run succeeds; later radial profile is monotonic and bounded. |
| 5 | Localized Heat Source | `Heat_Transfer_Module\Verification_Examples\localized_heat_source.mph` | Heat-source placement and peak-temperature behavior. | Batch run succeeds; later peak temperature appears near the source region. |
| 6 | Surface-Mount Package | `Heat_Transfer_Module\Power_Electronics_and_Electronic_Cooling\surface_mount_package.mph` | Electronics package heat spreading. | Batch run succeeds; later package temperature and heat-flux metrics are finite and plausible. |
| 7 | Thermal Contact, Electronic Package, and Heat Sink | `Heat_Transfer_Module\Thermal_Contact_and_Friction\thermal_contact_electronic_package_heat_sink.mph` | Contact-resistance and heat-sink assumptions. | Batch run succeeds; later metrics show a contact-driven temperature drop. |

References:

- COMSOL command line docs: https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_ref_running.38.31.html
- COMSOL LiveLink parameter update docs: https://doc.comsol.com/6.4/doc/com.comsol.help.llmatlab/llmatlab_introduction.2.30.html
- Thin Plate verification example: https://doc.comsol.com/6.4/doc/com.comsol.help.models.heat.thin_plate/thin_plate.html
- Electronic Chip Cooling example: https://doc.comsol.com/5.6/doc/com.comsol.help.models.heat.chip_cooling/chip_cooling.html
- Heat Conduction in a Slab example: https://doc.comsol.com/5.4/doc/com.comsol.help.models.heat.heat_conduction_in_slab/heat_conduction_in_slab.html
- Cylinder Conduction example: https://doc.comsol.com/6.4/doc/com.comsol.help.models.heat.cylinder_conduction/cylinder_conduction.html
- Localized Heat Source example: https://doc.comsol.com/6.3/doc/com.comsol.help.models.heat.localized_heat_source/localized_heat_source.html
- Surface-Mount Package example: https://doc.comsol.com/6.4/doc/com.comsol.help.models.heat.surface_mount_package/surface_mount_package.html
- COMSOL V&V model collection note: https://www.comsol.com/blogs/now-available-collection-of-comsol-verification-and-validation-models/
