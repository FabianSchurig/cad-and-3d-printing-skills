# /// script
# requires-python = ">=3.11"
# dependencies = ["manifold3d>=3.0", "trimesh>=4.0", "numpy>=1.26", "pillow>=10.0", "scipy>=1.11",
#                 "potracer>=0.0.4"]
# ///
"""Raised vector relief from a bitmap, wrapped exactly onto a cylinder or cone (Z axis), as a mesh.

Usage:
    uv run vector_relief.py art.png --surface-z 0,60 --surface-r 30,30 --art-z 10,50 \
        [--angle 270] [--span-deg 90] [--height 1.0] [--sink 0.4] [--union body.stl] [-o relief.stl]

  art.png        dark pixels are raised (--invert for light artwork, --threshold 0-255)
  --surface-z    z range of the conical/cylindrical face; --surface-r = radii at those two z values
  --art-z        bottom,top z of the artwork; --angle = artwork centre in degrees (0 = +X, 270 = -Y)
  --span-deg     angular width; default keeps the image aspect ratio at the mean radius
  --height       relief above the surface; --sink = overlap into the wall for a clean union
  --union        union the relief with this body mesh and write the combined part

Why a mesh: CAD emboss/wrap of hundreds of traced profiles on a curved face takes minutes to hours
per feature; trace + extrude + warp + boolean here takes seconds. Keep the CAD body as the source of
truth and apply the relief at print-prep time.

Warns about strokes narrower than --min-feature-mm (default 0.8 = two lines of a 0.4 mm nozzle).
Exit codes: 0 OK, 1 result is not a valid manifold, 2 usage error.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import manifold3d as m3d
import numpy as np
import potrace
import trimesh
from PIL import Image
from scipy import ndimage


@dataclass(frozen=True)
class Cone:
    """Surface of revolution about Z with radius linear in z (a cylinder when r0 == r1)."""

    z0: float
    z1: float
    r0: float
    r1: float

    def radius(self, z: np.ndarray | float) -> np.ndarray | float:
        return self.r0 + (z - self.z0) * (self.r1 - self.r0) / (self.z1 - self.z0)


@dataclass(frozen=True)
class Placement:
    """Where and how the artwork sits on the surface (lengths in mm, angles in degrees)."""

    z_bottom: float
    z_top: float
    angle_deg: float = 270.0
    span_deg: float | None = None  # None keeps the image aspect ratio at the mean radius
    height: float = 1.0
    sink: float = 0.4
    refine_mm: float = 1.0

    def validate(self, cone: Cone) -> None:
        if not min(cone.z0, cone.z1) <= self.z_bottom < self.z_top <= max(cone.z0, cone.z1):
            raise ValueError("--art-z must lie inside --surface-z")


def _bezier(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, n: int) -> np.ndarray:
    t = np.linspace(0, 1, n + 1)[1:, None]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3


def trace(mask: np.ndarray) -> list[np.ndarray]:
    """Closed polylines in pixel coordinates (x = column, y = row) around True pixels."""
    padded = np.pad(mask, 2)
    polylines = []
    for curve in potrace.Bitmap(~padded).trace(turdsize=10, alphamax=1.0, opticurve=True, opttolerance=0.3):
        p = np.array([curve.start_point.x, curve.start_point.y])
        pts = [p]
        for seg in curve.segments:
            end = np.array([seg.end_point.x, seg.end_point.y])
            if seg.is_corner:
                pts += [np.array([seg.c.x, seg.c.y]), end]
            else:
                c1, c2 = np.array([seg.c1.x, seg.c1.y]), np.array([seg.c2.x, seg.c2.y])
                length = np.linalg.norm(c1 - p) + np.linalg.norm(c2 - c1) + np.linalg.norm(end - c2)
                pts += list(_bezier(p, c1, c2, end, max(2, int(length / 2))))
            p = end
        polylines.append(np.array(pts[:-1]) - 2)
    return polylines


def count_thin_strokes(mask: np.ndarray, mm_per_px: float, min_mm: float) -> int:
    """Connected strokes whose widest point is narrower than min_mm."""
    labels, n = ndimage.label(mask)
    if n == 0:
        return 0
    widest = ndimage.maximum(ndimage.distance_transform_edt(mask), labels, index=np.arange(1, n + 1))
    return int((np.asarray(widest) * 2 * mm_per_px < min_mm).sum())


def build_relief(mask: np.ndarray, cone: Cone, place: Placement) -> tuple[m3d.Manifold, float]:
    """Relief manifold and its angular span in degrees."""
    place.validate(cone)
    h, w = mask.shape
    za, zb = place.z_bottom, place.z_top
    r_ref = float(cone.radius((za + zb) / 2))
    sy = (zb - za) / h
    span = math.radians(place.span_deg) if place.span_deg else w * sy / r_ref
    if not 0 < span < 2 * math.pi:
        raise ValueError("artwork span must be between 0 and 360 degrees")
    sx = span * r_ref / w
    polys = [np.column_stack([c[:, 0] * sx - span * r_ref / 2, zb - c[:, 1] * sy]) for c in trace(mask)]
    if not polys:
        raise ValueError("no artwork pixels found (check --invert/--threshold)")
    theta0 = math.radians(place.angle_deg)

    def warp(v: np.ndarray) -> np.ndarray:
        theta = theta0 + v[:, 0] / r_ref
        r = cone.radius(v[:, 1]) + v[:, 2]
        return np.column_stack([r * np.cos(theta), r * np.sin(theta), v[:, 1]])

    # One pointwise warp of the refined extrusion: an arc below 360 deg cannot self-intersect.
    section = m3d.CrossSection(polys, m3d.FillRule.EvenOdd)
    relief = (
        m3d.Manifold.extrude(section, place.sink + place.height)
        .translate((0, 0, -place.sink))
        .refine_to_length(place.refine_mm)
        .warp_batch(warp)
    )
    return relief, math.degrees(span)


def load_trimesh(path: str | Path) -> trimesh.Trimesh:
    """Load a file as one triangle mesh; reject anything else (empty scenes, point clouds)."""
    mesh = trimesh.load(path, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{path}: not a triangle mesh")
    return mesh


def to_manifold(mesh: trimesh.Trimesh) -> m3d.Manifold:
    return m3d.Manifold(m3d.Mesh(np.asarray(mesh.vertices, np.float32), np.asarray(mesh.faces, np.uint32)))


def to_trimesh(man: m3d.Manifold) -> trimesh.Trimesh:
    mesh = man.to_mesh()
    return trimesh.Trimesh(np.asarray(mesh.vert_properties)[:, :3], np.asarray(mesh.tri_verts), process=False)


def _pair(text: str) -> tuple[float, float]:
    a, b = (float(v) for v in text.split(","))
    return a, b


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("--surface-z", type=_pair, required=True)
    ap.add_argument("--surface-r", type=_pair, required=True)
    ap.add_argument("--art-z", type=_pair, required=True)
    ap.add_argument("--angle", type=float, default=270.0)
    ap.add_argument("--span-deg", type=float)
    ap.add_argument("--height", type=float, default=1.0)
    ap.add_argument("--sink", type=float, default=0.4)
    ap.add_argument("--invert", action="store_true")
    ap.add_argument("--threshold", type=int, default=128)
    ap.add_argument("--refine-mm", type=float, default=1.0, help="max edge length before warping")
    ap.add_argument("--min-feature-mm", type=float, default=0.8)
    ap.add_argument("--union")
    ap.add_argument("-o", "--out", default="relief.stl")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        cone = Cone(*args.surface_z, *args.surface_r)
        z_bottom, z_top = args.art_z
        place = Placement(z_bottom, z_top, args.angle, args.span_deg, args.height, args.sink, args.refine_mm)
        gray = np.asarray(Image.open(args.image).convert("L"))
        mask = gray > args.threshold if args.invert else gray < args.threshold
        relief, span_deg = build_relief(mask, cone, place)
        body = to_manifold(load_trimesh(args.union)) if args.union else None
    except Exception as err:
        print(f"usage error: {err}", file=sys.stderr)
        return 2

    thin = count_thin_strokes(mask, (place.z_top - place.z_bottom) / mask.shape[0], args.min_feature_mm)
    if thin:
        print(f"WARNING: {thin} strokes narrower than {args.min_feature_mm} mm will not print cleanly")
    result = relief if body is None else body + relief
    if result.status() != m3d.Error.NoError or result.is_empty():
        print(f"FAILED: manifold status {result.status()}", file=sys.stderr)
        return 1
    to_trimesh(result).export(Path(args.out))
    print(f"relief {relief.volume():.1f} mm3, {result.num_tri()} triangles, span {span_deg:.1f} deg")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
