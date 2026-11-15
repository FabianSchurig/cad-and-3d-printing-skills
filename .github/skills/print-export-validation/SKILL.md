---
name: print-export-validation
description: Export CAD bodies to print-ready meshes and gate them (watertight, single body, on the bed, fits the build volume, overhangs, volume vs. CAD), then prepare slicer projects and document what was checked. Use when exporting STL/3MF, preparing parts for printing, writing a print report, or handing printable files to someone.
---

# Print export & validation

## Export

- Export each body separately, named after the body, into the design's `out/raw/`. Use fine refinement (surface deviation ≈ 0.01–0.02 mm; in Fusion use custom refinement with surfaceDeviation 0.001 cm, because "High" is often too coarse for curved parts) so the mesh volume stays within 0.01 % of the BRep volume. Note each BRep volume (Fusion reports cm³).
- Never scale a mesh to make a variant; change parameters and re-export.

## Prepare

Mesh work runs outside the CAD tool (`trimesh` + `manifold3d`): orient each part for support-free printing, place it on z = 0 and centre it (`scripts/place_on_bed.py in.stl out.stl --rotate x:180`), union mesh-only detail (`mesh-surface-detail`), drop zero-volume slivers after simplification (`decompose()`, keep pieces > 1 mm³). Write a section image of mating parts to check fits by eye.

## Gate

```bash
uv run scripts/check_mesh.py out/*.stl --build-volume 256,256,256 --report out/print_report.txt
uv run scripts/check_mesh.py out/part.stl --brep-volume-cm3 12.5 --json
```

| Finding | Severity | Meaning |
|---|---|---|
| `watertight`, `winding_consistent`, `bodies`, `on_bed`, `positive_volume` | error | Slicers misbehave or the part is not what was modelled |
| `volume_vs_brep` (> 0.01 %), `build_volume` | error | Export too coarse, wrong body, or does not fit the printer |
| `triangles` (> 2 M), `degenerate_faces`, `xy_centred` | warning | Slow slicing or sloppy placement |
| `overhang_area` | info | Look at where it is: a few mm² at hole tops is fine |

Exit code 0 = OK, 1 = FAILED, 2 = unreadable input. A raw export not yet on the bed fails `on_bed` on purpose.

## Slicer & hand-off

- Ship slicer **project** files (Bambu Studio / OrcaSlicer `.3mf` with printer, filament and process) next to printer-independent STL/3MF.
- When the user already has a project, update it instead of rebuilding it: `uv run scripts/update_3mf_project.py old.3mf new.3mf --replace "Object name=out/print/part.stl"` (`--list` shows the names). This keeps presets, plates and positions, and drops stale G-code.
- Slice from the command line, including a Windows slicer from WSL: [references/slicer-cli.md](references/slicer-cli.md).
- A CLI slice confirms the part slices in-bounds without supports; record slicer version, layer count, time and filament estimates. Never invent printer presets and never reuse a toolpath on another printer or nozzle.
- Keep **"slice checked"** and **"physically printed / fit-tested"** apart in README and manifest.
- Never send a job to a printer unless asked.
- Document per part: orientation, layer height, walls/infill, supports, brim, hardware and assembly steps.
