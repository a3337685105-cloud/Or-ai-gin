# Plot Accuracy QA

## Priority

This layer treats visual style as secondary. The first question is whether the
exported figure still means what the user asked for:

- Axis titles must be declared in `PlotSpec`, then written into Origin and read
  back from the graph object metadata.
- Label text must avoid hard encoding replacement markers, so column names such
  as `two_theta_deg`, `Raman_shift_cm-1`, or `Intensity_a.u.` are not silently
  damaged.
- If linear fitting is enabled, the deterministic regression result must exist
  and Origin must render a fit-line object.
- For routed XRD/Raman line plots, the workflow detects peak candidates from the
  original numeric table and asks Origin to render peak marker objects.

## Current Implementation

`evaluation/plot_accuracy.py` produces deterministic checks and writes
`plot_accuracy.json` for every workflow run. The report records expected axis
titles, peak candidates, Origin render metadata when available, and pass/fail
checks that are also copied into `result.json`.

Origin is still a generator, not the source of truth. The workflow computes
regression and peak candidates from the original data, passes explicit objects
to `OriginClient`, exports a new image/project, and stores
`origin_render_metadata.json` for reproducibility.

## Limits

This is not OCR yet. Axis-title correctness is verified by reading Origin graph
object metadata after setting it, not by recognizing text pixels in the PNG.
That is stronger than pure image-health checks, but a future release should add
OCR or template-level object extraction for independent render verification.

AI can help decide which route or analysis family applies, but it should not
override these validators. If AI output is uncertain, the script should ask for
clarification or fail closed.
