---
name: print-failure-diagnosis
description: Diagnose a failed, warped, stringy or badly fitting 3D print with a tight test loop, falsifiable hypotheses and one change at a time, then encode the fix as a spec rule or check. Use when a print fails, does not fit its mating part, breaks, warps, or shows quality defects.
---

# Print failure diagnosis

## 1. Build the loop first (this is the skill)

Find the fastest repeatable signal that shows the defect: a caliper reading of the real part, a cut-down test coupon (just the failing feature, a few minutes to print), a tolerance ladder, or a `check_part.py` probe reproducing the misfit in the model. Without a loop you are guessing.

## 2. Reproduce and minimise

Confirm the defect on the coupon. Record printer, nozzle, material (brand, colour, dryness), slicer version, profile and orientation.

## 3. Hypotheses

Write 3-5 ranked, falsifiable hypotheses, each with the test that would refute it. Example: "Hole 0.3 mm undersize from first-layer squish → a coupon with a 0.3 mm base chamfer fits".

| Symptom | Usual suspects |
|---|---|
| Fit too tight / loose | Clearance per side, XY hole compensation, elephant's foot, measuring the wrong datum |
| Warping, corner lift | Bed adhesion, sharp base corners, enclosure/draft, material |
| Drooping overhangs, bad bridges | Angle > ~50°, bridge > ~10 mm, cooling, orientation |
| Layer splits, weak part | Load across layers (orientation), temperature, too few walls |
| Blurry fine detail | Feature narrower than two extrusion widths, layer height |

## 4. Change one variable per test

Measure before and after with the same instrument. Stop when one hypothesis survives and its fix reproduces.

## 5. Encode the lesson

Fix it where it lives (spec value, model parameter, slicer setting, material handling), add a regression check to `checks.json` or a rule to `spec.md`, and log hypothesis, evidence and result in `progress.md`.
