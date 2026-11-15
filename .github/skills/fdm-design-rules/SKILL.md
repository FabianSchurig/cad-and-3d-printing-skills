---
name: fdm-design-rules
description: Geometric design rules for FFF/FDM 3D-printed parts (wall thickness, holes, overhangs, bridges, clearances, pins, threads, embossed text, base edges, print orientation, part splitting). Use when designing or reviewing a part that will be 3D printed, choosing fit clearances, splitting a large part, or checking whether geometry prints without supports.
---

# FDM design rules

## Design for the process first

Before modelling, record printer, nozzle, layer height, material and print orientation in the design's `spec.md`. Every rule below scales with them; the defaults assume a 0.4 mm nozzle (≈ 0.45 mm extrusion width) and 0.2 mm layers. Put the values you use into user parameters or the model's `Params`, not into literals.

## Rules

| Feature | Starting value | Notes |
|---|---|---|
| Wall thickness | ≥ 0.9 mm (2 extrusion widths) | More perimeters for strength |
| Minimum feature / pin Ø | ≥ 1.8 mm (4 extrusion widths) | Use bought pins for functional joints |
| Hole Ø | ≥ 2 mm | Undersize and drill when accuracy matters |
| Clearance between mating parts | ~0.2 mm loose, ~0.1 mm tight (per side) | Calibrate with a tolerance coupon on your printer |
| Overhang | < 50° from vertical | Many current printers manage up to ~70° |
| Unsupported bridge | < 10 mm | |
| Unsupported horizontal ledge | < 0.9 mm | |
| Emboss (raised) | ≥ 0.9 mm wide; ≤ 0.9 mm proud on vertical faces | |
| Engrave (recessed) | ≥ 0.5 mm wide | |
| Base edges (no brim) | ~0.3 mm chamfer | Against elephant's foot |
| Base corners of large parts | radius ≥ 4 mm | Reduces warping |
| Downward-facing edges | chamfer, not fillet | |
| Modelled threads | ≥ M5, vertical holes only | |
| Holes for tap / self-tapping screw / heat-set insert | 90 % / 96 % / 98 % of the major Ø | |
| Horizontal holes | small flat or teardrop top (~1 layer height) | Against droop |
| Holes over unsupported bridges | two stacked bridging rectangles: 1× and 2× layer height | |

Source: Hydra Research, [Design Rules for FFF 3D Printing](https://www.hydraresearch3d.com/design-rules). These are starting values; your printer and material decide. Verify fits with a coupon (`print-failure-diagnosis`) and record calibrated values in the spec.

## Orientation and splitting

- Choose the orientation while designing: large flat face on the bed, critical round features vertical, layer lines across the main load path.
- Split tall or complex parts into pieces that print without supports; split planes are user parameters. Join with centring spigots/collars, bayonets, or a threaded rod with nut traps using the fit clearance above. Printing a piece upside down often removes supports.
- Nut traps: across-flats + ~0.4 mm; on the bed side a hex pocket bridges cleanly. A bore printed over open space can get a 1–2 layer sacrificial skin, drilled out after printing.
- Raised text: letters at least the emboss width; after a CAD emboss check that every glyph contour survived.

## Closures, lids and seals

- A lid that must stay shut under airflow, vibration or pressure needs a **positive lock**: a slide-on dovetail or rail, a bayonet, or a snap hook with a detent. A friction plug of one or two perimeters loosens after a few cycles and pops open under pressure.
- Dust and debris seals: never a straight butt gap. Use an overlap or a labyrinth (at least one change of direction, overlap ≥ 2 × the clearance), and check it at maximum play, not only at rest (`check_assembly.py` → `line_of_sight`).
- Inside a container, avoid upward-facing ledges where debris settles and where a seam can be pressed open: let walls run as one continuous face, and slope inner shelves to ≥ 45°.
- Snap arms: bend along the layer lines, not across them, and keep strain low (a long thin arm, not a short thick one). Prove the snap feel with a test print.

## Material

- PLA softens in hot cars and in sunlight: use PETG, ASA or ABS there. PETG still creeps under sustained load and heat.
- For non-certified accessories near safety-relevant parts (child-seat anchors, restraints, tie-downs), state that they carry no load rating and must not interfere with the safety function.
