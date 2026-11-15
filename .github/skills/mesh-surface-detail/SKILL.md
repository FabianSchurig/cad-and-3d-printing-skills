---
name: mesh-surface-detail
description: Add printable surface detail to a CAD body as a mesh step - raised or engraved artwork, logos and text wrapped onto cylinders and cones, or displacement textures - and union it robustly. Use when embossing artwork on curved surfaces, adding textures or knurling, or when CAD emboss/wrap features are too slow.
---

# Mesh surface detail

Keep the CAD body as the source of truth and add detail at print-prep time as a mesh. Embossing hundreds of traced profiles on a curved face can take a CAD kernel hours; a mesh pipeline does it in seconds.

## Choose the technique

| Detail | Technique |
|---|---|
| Logo, text, single artwork at an exact place | Vector relief: trace → extrude → wrap → union (`vector_relief.py`) |
| Repeating texture (knurl, leather, grip) over a large area | Displacement map along smooth vertex normals (e.g. [BumpMesh](https://github.com/CNCKitchen/stlTexturizer), a separate AGPL tool) |
| A few simple letters on a flat or simple face | Native CAD emboss is fine |

## Vector relief on a cylinder or cone

```bash
uv run scripts/vector_relief.py art.png --surface-z 0,60 --surface-r 30,27 --art-z 10,50 \
    --angle 270 --height 1.0 --sink 0.4 --union out/body.stl -o out/body_with_relief.stl
```

- Dark pixels are raised (`--invert` for light artwork). The angular span keeps the image aspect ratio unless `--span-deg` is given; `--angle 270` centres the art on the −Y (front) side.
- `--sink` overlaps the relief into the wall so the union is clean; keep it below the wall thickness.
- The script warns about strokes narrower than `--min-feature-mm` (0.8 mm = two lines of a 0.4 mm nozzle). Thicken lines in the artwork rather than hoping they print.
- Then run `check_mesh.py` on the result: one body, watertight, volume grew by roughly the relief volume.

## Printability

- Relief height 0.6–1.2 mm, feature width ≥ 2 extrusion widths, engraved gaps ≥ 0.5 mm.
- Relief on a downward-facing surface is an overhang: orient the part so detailed faces are vertical or upward.
- Keep triangle counts sane (≤ 2 M for slicers); refine edge length ≈ 1 mm on gentle curves.
