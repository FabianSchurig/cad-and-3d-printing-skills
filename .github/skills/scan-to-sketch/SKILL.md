---
name: scan-to-sketch
description: Turn a flatbed scan or orthographic photo of an existing part into a calibrated 2D outline (DXF/SVG plus JSON manifest with scale state and uncertainty) to remodel it in CAD. Use when reverse-engineering, remodelling or copying a physical part from scans, photos and caliper measurements.
---

# Scan to sketch

## Capture

- Flatbed: highest **optical** resolution (no interpolation), part flat on the glass, dark matte backing or open lid in a dark room, no shadows. Depth of field is shallow: features away from the glass shift and blur.
- Photo: only for roughly flat parts; camera perpendicular, far away with zoom (less perspective), the reference ruler or gauge at the same height as the outline.
- Always measure at least one caliper dimension per axis on a sharp, flat edge. A gauge pin or coin on the glass is a good second reference.

## Extract

```bash
uv run scripts/scan_to_outline.py scan.png --calib x1,y1,x2,y2,<mm> [--calib ... along Y] -o out/
```

- Pick calibration points on sharp edges in the original scan (not an enhanced copy). Two calibrations, one per axis, give separate X/Y scales; flatbed sensor and transport axes differ by fractions of a percent.
- `--dpi` alone gives a **nominal** scale; the manifest flags it. Never model from a nominal scale.
- Outputs: `*_outline.dxf` (mm, Y up, OUTLINE/HOLES layers, circles as true circles), `*_outline.svg`, `*_overlay.png` (check it!), `*_outline.json` (scale state, source, edge uncertainty, shapes).
- `--invert` for light parts on dark backgrounds; `--mirror` when the part was scanned face-down and you want the view from above.

## Hand off to CAD

- Fusion: insert the DXF as a sketch, or let a script (see `fusion-api-scripting`) create fitted lines, arcs and splines from the JSON.
- build123d: read the JSON; build profiles from circles and simplified polylines.
- Replace raw polylines with constrained lines, arcs and a few fair splines. Caliper dimensions override scan values; record each value as measured / derived / assumed in `spec.md`.

## Honesty rules

- Report the scale state and uncertainty (≈ 2 px) with every derived dimension.
- Edge maps show shadows and texture as edges and can miss faint real edges: confirm on the overlay.
- Do not invent unseen faces or hidden features; list them as open questions.
