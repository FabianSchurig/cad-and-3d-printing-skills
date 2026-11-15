---
name: fusion-parametric-modeling
description: Plan and build clean, parameter-driven Autodesk Fusion designs with an ordered, named timeline, and derive size variants from parameters. Use when starting a new Fusion part, restructuring a messy timeline, adding user parameters, remodelling a part from measurements or scans, or generating several size variants of a part.
---

# Parametric modelling in Fusion

## 1. Plan the feature order first

Before creating any geometry, write the plan into the design's `progress.md` and let the user confirm it. The plan should cover:

- the user parameters (name, expression, unit, comment);
- the timeline groups in build order, e.g. `01 Base profile` → `02 Split into print parts` → `03 Hollowing` → `04 Joints` → `05 Details/text`;
- which features cut or join which bodies, and where the print splits and fits go.

Standard order: base sketches and solids → splits → shell/cavities → joints/fits → details (fillets, chamfers, text, patterns). Put cosmetic and slow features (text, emboss, patterns) last, so earlier edits recompute quickly.

## 2. User parameters drive every key dimension

- Every dimension someone might change gets a user parameter, at least overall width/length/height and wall thickness. Each parameter has a comment explaining what it is and where the value comes from.
- Derive dependent values by expression (`pocket_d = cable_d + fit_clearance_d`) instead of copying numbers.
- Bind sketch dimensions to parameter expressions. Reference the nearest datum (`Z_cut2 + 4 mm`), not absolute magic numbers, so moving a split plane moves everything above it.
- Keep fit tolerances as their own parameters (e.g. `tol_fit = 0.2 mm`). Never bake them into other numbers.
- Text content can be a text parameter too.
- **Every sketch is fully constrained** (black, not blue): each point is fixed by a dimension or a constraint to a datum. A blue sketch moves unpredictably when a parameter changes. Check `sketch.isFullyConstrained` for all sketches before hand-off, including sketches that were in the design before you started.
- Reference geometry relative to a datum, so moving one feature moves its dependants: a lid, its rails and the cuts that clear old material should all follow one height parameter instead of repeating its value.

## 3. Name everything and group the timeline

- Name every sketch (`Sk_...`), feature, construction plane and body. Body names should match what will be exported (`A_Base`, `B_Column`, ...).
- After each stage, collapse its features into a numbered timeline group: `timelineGroups.add(start, end)`, set its name, `isCollapsed = True`.

## 4. Replacing a feature: retire the old one

When a redesign replaces a body or feature (a new lid, a new mount), delete the old bodies, sketches, features, joints and parameters in the same change. Do not hide them or leave them "for reference". Leftovers confuse the next edit, can still cut or join geometry, and leave seams on faces they touched. After deleting, compare body volumes and timeline health with before, and look at the faces next to the removed feature.

## 5. Measured vs. assumed

Dimensions, their sources and tolerances live in the design's `spec.md` (see `cad-spec`); parameter comments cite the spec row ID (`D3: measured`). When remodelling from scans, keep reference contours in clearly named sketches (`..._SCAN_CONTOUR_UNVERIFIED`), separate from design curves, and prefer a few constrained lines, arcs and fair curves over splines through noisy points (see `scan-to-sketch`). Store assumptions in the design too (`root.attributes.add(group, "assumptions", json)`).

## 6. Prove the model really is parametric

Change a key parameter in a disposable copy (or undo afterwards) and verify that the geometry follows: bounding box, slot sizes, volumes. A model that only *looks* parametric breaks on the first variant.

## 7. Variants are regenerated, never scaled

Generate each size by setting parameters and re-exporting; uniform mesh scaling also scales walls, hooks and clearances. Follow the size-variants playbook of `cad-workflow` for naming and manifests.
