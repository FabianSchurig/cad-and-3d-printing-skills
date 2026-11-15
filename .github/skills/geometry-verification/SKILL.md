---
name: geometry-verification
description: Verification-first CAD loop - write acceptance checks (extents, volume, wall thickness, open bores, solid regions, single watertight body) before modelling, watch them fail, model until they pass, and render previews. Use when building or changing any part, fixing a fit, or claiming a model meets its spec.
---

# Geometry verification (red → green)

## Loop

1. **Checks first.** Write `checks.json` from the spec (see `cad-spec`). Expected values come from spec rows and caliper readings, never from the model's own parameters; a check that recomputes the model's formula proves nothing.
2. **Red.** Run the checks against the current or a placeholder export and confirm each one fails for the reason you expect. A check is only trusted once it has been seen to fail.
3. **Model one feature group**, export, run the checks. Repeat until green.
4. **Never shrink to pass.** Fix the model, or change the spec with the user's agreement and a change-log entry.

```bash
uv run scripts/check_part.py checks.json out/part.stl          # exit 0 pass, 1 fail, 2 usage, 3 nothing checked
uv run --with build123d scripts/check_part.py checks.json out/part.step
```

## `checks.json`

```json
{
  "file": "out/part.stl",
  "checks": {
    "bodies": 1,
    "watertight": true,
    "extents": {"x": [39.9, 40.1], "z": [9.9, 10.1]},
    "volume_mm3": [7000, 8000],
    "material_at": [{"at": [10, 0, 5], "why": "D3: flank must be solid"}],
    "empty_at": [{"at": [0, 0, 5], "why": "D2: bore open"}],
    "min_wall": {"mm": 0.9, "max_thin_fraction": 0.002}
  }
}
```

- `material_at` / `empty_at` probes are the most powerful checks: one point per bore, slot, pocket, insertion path and critical solid region. Place probes mid-feature, not on a surface.
- `min_wall` samples the surface and ray-casts inward. It cannot see features below mesh resolution and skips inside corners; it reports the 1st-percentile thickness.
- Ranges encode tolerance. Use the spec tolerance, not a range wide enough to always pass.
- **Datums instead of copied numbers.** Put named spec values in a top-level `"datums": {"z_top": 10}` and write coordinates as `"z_top - 2.5"`. When a feature moves, edit one datum, not every probe. Datum values still come from the spec, never from the model.
- A probe placed on a surface or in the wrong feature gives a false red or green. When a probe surprises you, check which feature it actually sits in before you change the model.

## Assemblies, moving parts and seals

`check_assembly.py` checks mating parts exported in **one shared frame**. If parts come from different components, export them in the same coordinate system or record the offset in the spec's Frames section.

```bash
uv run scripts/check_assembly.py assembly.json        # same exit codes as check_part.py
```

| Question | Check |
|---|---|
| Do the parts collide at rest or in a pose? | `interference` |
| Can the lid/drawer slide in and out? | `slide_path` (stepped motion, worst overlap) |
| Does a rail, latch or detent really block a direction? | `held` (move by the play, expect overlap in a region) |
| Can dust, light or air pass straight through a seam? | `line_of_sight` (axis-parallel rays over a window) |
| Will dirt collect on ledges inside? | `upward_faces` |

- **Check every moving part in several poses**: closed, partly open, at the end stop, and lifted by its clearance. A check run only at rest passes on a part that cannot move at all. Watch for that in the red run: a check that is green on the old design may be trivially green.
- A seal is proved by *no line of sight* through every seam at rest **and** at maximum play, not by touching faces. Model labyrinths or overlaps, then show the straight-gap version fails the check.
- `line_of_sight` only tests axis-parallel lines. For slanted seams, cut the region with several windows or write a design-specific check next to the model.

## Which check for which change

| Change | Check |
|---|---|
| Outer size, height | `extents` |
| Hole, slot, pocket, clearance path | `empty_at` probes along the path |
| Rib, boss, floor, flank | `material_at` probes |
| Shell, thin features | `min_wall` |
| Boolean or split operations | `bodies`, `watertight`, `volume_mm3` |
| Fits, sliding lids, seals, latches | `check_assembly.py`, in several poses |
| Removed an old feature | `empty_at` where it was; face count of the surface it left (one face, no seam) |
| Fusion timeline changes | timeline health + the checks above (see `fusion-api-scripting`) |

## Previews

```bash
uv run scripts/render_preview.py out/part.stl --views iso,front,top -o out/preview
```

Render only when visible geometry changed and look at the image once. Section images of several parts are only meaningful if all meshes share one frame; a part drawn in the wrong place sends the next session the wrong way. Use pictures for arrangement and obvious errors; read numbers from checks, never from images.
