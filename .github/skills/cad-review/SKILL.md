---
name: cad-review
description: Two-axis review of a part before export or release - (1) printability and model hygiene against FDM rules and parametric conventions, (2) conformance to the spec and its acceptance checks - with every finding backed by a measurement. Use when a part is ready for export, release or printing, or when the user asks to review a design.
---

# CAD review

Run two independent reviews, each in a **fresh subagent** that receives only file paths (design folder, spec, checks, model script, exports), not this conversation. Report them side by side; do not merge them.

## Axis 1 – Printability and hygiene

Inputs: `fdm-design-rules`, `fusion-parametric-modeling` or `build123d-modeling`, the model and the exported mesh.

- Walls, holes, pins, text, overhangs, bridges against the process recorded in the spec.
- Print orientation, bed contact, elephant's-foot chamfers, support needs.
- Parameters drive key dimensions; names and timeline groups (or model-script structure) are clean; no magic numbers that belong in the spec.
- **No leftovers from earlier versions.** The body, component and sketch list matches the spec's part list; obsolete bodies, sketches, features, joints and parameters are deleted, not hidden. Fusion: list them with a read-only script (see `fusion-api-scripting`).
- **Sketches fully constrained.** Every sketch reports `isFullyConstrained`. A blue (under-constrained) sketch is a should-fix finding.
- **Clean surfaces.** An intended continuous wall or floor is a single face, with no seam, sliver or leftover cut. Evidence: the face count on that plane, or the faces hit by a probe line.
- **Fits, seals and moving parts** are checked with `check_assembly.py` in several poses (at rest, partly open, at the end stop, lifted by the play).

## Axis 2 – Spec conformance

Inputs: `spec.md`, `checks.json`, `check_part.py` and `check_mesh.py` output.

- Every requirement maps to a check or to "verified by print test"; list unmapped requirements.
- Every check's expected value traces to a spec row; flag checks derived from the model itself.
- Re-run the checks; report the result lines.

## Rules for findings

- A finding counts only with evidence: a check result, a probe point, a measured distance, a preview showing the defect. "Looks thin" is not a finding; "min_wall p1 = 0.55 mm at the hook tip" is.
- Each finding: severity (blocker / should-fix / note), location, evidence, suggested fix. Keep each axis report under 400 words.
