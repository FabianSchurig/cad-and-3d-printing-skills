# /// script
# requires-python = ">=3.11"
# dependencies = ["vtk>=9.3"]
# ///
"""Render headless PNG previews of a mesh or STEP file for visual review.

Usage:
    uv run render_preview.py part.stl [--views iso,front,top] [--size 640x480] [-o out/]
    (STEP input: uv run --with build123d render_preview.py part.step)

Writes <stem>_<view>.png per view (iso, front, back, left, right, top, bottom), each labelled
with the view name and bounding-box size. Use the images for shape and arrangement only; read
dimensions from checks, never from pictures. Runs without a display (offscreen rendering).

Exit codes: 0 OK, 2 usage error.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import vtk

Vec3 = tuple[float, float, float]
VIEWS: dict[str, tuple[Vec3, Vec3]] = {  # direction from focal point to camera, view-up
    "iso": ((1, -1, 0.8), (0, 0, 1)),
    "front": ((0, -1, 0), (0, 0, 1)),
    "back": ((0, 1, 0), (0, 0, 1)),
    "left": ((-1, 0, 0), (0, 0, 1)),
    "right": ((1, 0, 0), (0, 0, 1)),
    "top": ((0, 0, 1), (0, 1, 0)),
    "bottom": ((0, 0, -1), (0, -1, 0)),
}
READERS = {".stl": vtk.vtkSTLReader, ".obj": vtk.vtkOBJReader, ".ply": vtk.vtkPLYReader}


def step_to_stl(path: Path, out_dir: Path) -> Path:
    try:
        from build123d import export_stl, import_step
    except ImportError as err:
        raise RuntimeError(
            "STEP input needs build123d: uv run --with build123d render_preview.py ..."
        ) from err
    stl = out_dir / f"{path.stem}.stl"
    export_stl(import_step(str(path)), str(stl), tolerance=0.02, angular_tolerance=0.2)
    return stl


def read_polydata(path: Path) -> vtk.vtkPolyData:
    reader_cls = READERS.get(path.suffix.lower())
    if reader_cls is None:
        raise ValueError(f"unsupported format {path.suffix} (use STL/OBJ/PLY/STEP)")
    reader = reader_cls()
    reader.SetFileName(str(path))
    reader.Update()
    poly = reader.GetOutput()
    if poly.GetNumberOfPoints() == 0:
        raise ValueError(f"{path} contains no geometry")
    return poly


def render_view(poly: vtk.vtkPolyData, view: str, size: tuple[int, int], out: Path) -> None:
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(poly)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(0.85, 0.55, 0.2)
    actor.GetProperty().SetSpecular(0.2)

    b = poly.GetBounds()
    label = vtk.vtkTextActor()
    label.SetInput(f"{view}  {b[1] - b[0]:.1f} x {b[3] - b[2]:.1f} x {b[5] - b[4]:.1f} mm")
    label.GetTextProperty().SetColor(0, 0, 0)
    label.GetTextProperty().SetFontSize(14)

    renderer = vtk.vtkRenderer()
    renderer.SetBackground(1, 1, 1)
    renderer.AddActor(actor)
    renderer.AddViewProp(label)
    direction, up = VIEWS[view]
    centre = ((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, (b[4] + b[5]) / 2)
    cam = renderer.GetActiveCamera()
    cam.SetFocalPoint(*centre)
    cam.SetPosition(*(c + d for c, d in zip(centre, direction, strict=True)))
    cam.SetViewUp(*up)
    renderer.ResetCamera()

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(*size)
    window.AddRenderer(renderer)
    window.Render()
    grab = vtk.vtkWindowToImageFilter()
    grab.SetInput(window)
    grab.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(out))
    writer.SetInputConnection(grab.GetOutputPort())
    writer.Write()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--views", default="iso,front,top")
    ap.add_argument("--size", default="640x480")
    ap.add_argument("-o", "--out", default=".")
    args = ap.parse_args(argv)

    views = args.views.split(",")
    try:
        unknown = [v for v in views if v not in VIEWS]
        if unknown:
            raise ValueError(f"unknown views {unknown}; choose from {', '.join(VIEWS)}")
        width, height = (int(v) for v in args.size.lower().split("x"))
        src, out = Path(args.file), Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            mesh_path = step_to_stl(src, Path(tmp)) if src.suffix.lower() in (".step", ".stp") else src
            poly = read_polydata(mesh_path)
    except Exception as err:
        print(f"usage error: {err}", file=sys.stderr)
        return 2
    for view in views:
        png = out / f"{src.stem}_{view}.png"
        render_view(poly, view, (width, height), png)
        print(png)
    return 0


if __name__ == "__main__":
    sys.exit(main())
