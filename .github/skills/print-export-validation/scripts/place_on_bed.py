# /// script
# requires-python = ">=3.11"
# dependencies = ["trimesh>=4.0", "numpy>=1.26"]
# ///
"""Orient a mesh for printing: rotate, then centre it in xy and put its lowest point on z = 0.

Usage:
    uv run place_on_bed.py in.stl out.stl [--rotate x:180,z:90] [--centre 0,0]

Rotations are applied in the given order about the world axes (degrees). Typical use: a lid
modelled top-up is printed top-down with --rotate x:180. The output passes check_mesh's on_bed
and xy_centred findings by construction; run check_mesh afterwards for everything else.

Exit codes: 0 written, 1 result not on the bed (should not happen), 2 usage error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import trimesh


def parse_rotations(text: str) -> list[tuple[str, float]]:
    out = []
    for item in filter(None, (s.strip() for s in text.split(","))):
        axis, _, deg = item.partition(":")
        if axis not in ("x", "y", "z") or not deg:
            raise ValueError(f"rotation {item!r} must look like x:180")
        out.append((axis, float(deg)))
    return out


def place(
    mesh: trimesh.Trimesh, rotations: list[tuple[str, float]], centre: tuple[float, float]
) -> trimesh.Trimesh:
    m = mesh.copy()
    for axis, deg in rotations:
        vec = np.eye(3)["xyz".index(axis)]
        m.apply_transform(trimesh.transformations.rotation_matrix(np.radians(deg), vec))
    lo, hi = m.bounds
    m.apply_translation([centre[0] - (lo[0] + hi[0]) / 2, centre[1] - (lo[1] + hi[1]) / 2, -lo[2]])
    return m


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--rotate", default="", help="comma-separated axis:degrees, applied in order")
    ap.add_argument("--centre", default="0,0", help="target xy of the bounding-box centre")
    args = ap.parse_args(argv)
    try:
        rotations = parse_rotations(args.rotate)
        cx, cy = (float(v) for v in args.centre.split(","))
        mesh = trimesh.load(args.src, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
            raise ValueError(f"{args.src}: not a triangle mesh")
    except Exception as err:
        print(f"usage error: {err}", file=sys.stderr)
        return 2
    placed = place(mesh, rotations, (cx, cy))
    placed.export(Path(args.dst))
    lo, hi = placed.bounds
    print(f"wrote {args.dst}: extents {np.round(hi - lo, 3).tolist()} min z {lo[2]:.4f}")
    return 0 if abs(lo[2]) < 1e-6 else 1


if __name__ == "__main__":
    sys.exit(main())
