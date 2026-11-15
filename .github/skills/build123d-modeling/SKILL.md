---
name: build123d-modeling
description: Model printable parts as headless, parametric Python code-CAD with build123d (OpenCASCADE) and export STEP/STL/3MF - no GUI CAD needed, runs in a container or CI. Use when the user has no Fusion document, wants a scriptable or reproducible part, or wants variants generated from parameters.
---

# build123d code-CAD

Use code-CAD when the part is parametric and needs no Fusion-specific feature, or no Fusion document exists. Prefer build123d (typed, explicit); CadQuery is acceptable if a project already uses it. pythonocc is too low-level for agent-written code.

## Model script contract

One `model/model.py` per design, runnable with `uv run`:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["build123d>=0.9"]
# ///
"""<Part> - parameters mirror spec.md rows."""

from dataclasses import dataclass
from pathlib import Path

from build123d import Box, Cylinder, Part, Pos, export_step, export_stl, fillet, Axis

OUT = Path(__file__).resolve().parent.parent / "out"


@dataclass(frozen=True)
class Params:
    width: float = 40.0  # D1
    depth: float = 20.0  # D2
    height: float = 10.0  # D3
    bore: float = 3.4  # D4: M3 clearance
    edge_r: float = 2.0


def build(p: Params = Params()) -> Part:
    part = Pos(0, 0, p.height / 2) * Box(p.width, p.depth, p.height)
    part -= Pos(0, 0, p.height / 2) * Cylinder(p.bore / 2, p.height)
    return fillet(part.edges().filter_by(Axis.Z), p.edge_r)


if __name__ == "__main__":
    part = build()
    assert part.is_valid and len(part.solids()) == 1
    OUT.mkdir(exist_ok=True)
    export_step(part, str(OUT / "part.step"))
    export_stl(part, str(OUT / "part.stl"), tolerance=0.01, angular_tolerance=0.1)
    print(f"volume {part.volume:.2f} mm3, bbox {part.bounding_box().size}")
```

- **Parameters** in one frozen dataclass whose comments cite spec row IDs. Variants are `build(Params(width=50))`, never scaling.
- **Model in print orientation**: Z up, bed face at z = 0.
- **Prints one summary line**; numbers for decisions come from `check_part.py`, not from this output.
- Mesh tolerance: linear ≈ 0.01 mm (about a tenth of the smallest clearance), angular 0.1 rad.

## Idioms and pitfalls

See [the cheat sheet](references/cheatsheet.md) for algebra-mode operations, selectors and common errors.

## Verify

Then follow `geometry-verification` (`check_part.py` on `out/part.stl`) and `print-export-validation` (`check_mesh.py`). Run the model again after every parameter change; the export is the artefact under test.
