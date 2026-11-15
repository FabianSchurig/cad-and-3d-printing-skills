# /// script
# requires-python = ">=3.11"
# dependencies = ["trimesh>=4.0", "numpy>=1.26", "scipy>=1.11", "networkx>=3.0"]
# ///
"""Printability gate for exported meshes (STL/3MF/OBJ/PLY).

Usage:
    uv run check_mesh.py part.stl [more.stl ...] [--overhang 50] [--brep-volume-cm3 12.5]
                         [--build-volume 256,256,256] [--json] [--report report.txt]

Per file: watertight, consistent winding, exactly one body, resting on z = 0, fits the build
volume, volume (optionally vs. the CAD BRep volume), downward-facing area steeper than the
overhang limit (faces on the bed excluded), triangle count, degenerate faces, XY centring.

Exit codes: 0 OK, 1 FAILED (an error-severity check failed), 2 usage error / unreadable file.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

BED_TOL_MM = 0.05
MAX_TRIANGLES = 2_000_000
VOLUME_TOL_PCT = 0.01
CENTRE_TOL_MM = 0.5


@dataclass(frozen=True)
class Finding:
    code: str
    ok: bool
    value: Any
    limit: Any = None
    unit: str = ""
    op: str = ""
    severity: str = "error"  # error fails the gate; warning/info are reported only


@dataclass(frozen=True)
class MeshReport:
    file: str
    extents_mm: list[float]
    volume_cm3: float | None
    findings: list[Finding]

    @property
    def ok(self) -> bool:
        return all(f.ok for f in self.findings if f.severity == "error")


def load_trimesh(path: str | Path) -> trimesh.Trimesh:
    """Load a file as one triangle mesh; reject anything else (empty scenes, point clouds)."""
    mesh = trimesh.load(path, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{path}: not a triangle mesh")
    return mesh


def overhang_area_mm2(mesh: trimesh.Trimesh, overhang_deg: float) -> float:
    """Area of faces pointing down more steeply than overhang_deg from vertical, off the bed."""
    limit = -np.cos(np.radians(90 - overhang_deg))
    above_bed = mesh.triangles[:, :, 2].max(axis=1) > mesh.bounds[0][2] + BED_TOL_MM
    steep = (mesh.face_normals[:, 2] < limit) & above_bed
    return float(mesh.area_faces[steep].sum())


def check(
    path: str | Path,
    overhang_deg: float = 50.0,
    brep_volume_cm3: float | None = None,
    build_volume: list[float] | None = None,
) -> MeshReport:
    mesh = load_trimesh(path)
    watertight, winding = bool(mesh.is_watertight), bool(mesh.is_winding_consistent)
    lo, hi = mesh.bounds
    ext = hi - lo
    bodies = len(mesh.split(only_watertight=False))
    vol_cm3 = float(mesh.volume) / 1000 if watertight else None
    centre = float(np.hypot(*((lo[:2] + hi[:2]) / 2)))

    findings = [
        Finding("watertight", watertight, watertight, True),
        Finding("winding_consistent", winding, winding, True),
        Finding("bodies", bodies == 1, bodies, 1, op="=="),
        Finding("on_bed", bool(abs(lo[2]) <= BED_TOL_MM), round(float(lo[2]), 4), 0.0, "mm", "min z =="),
        Finding(
            "positive_volume",
            vol_cm3 is None or vol_cm3 > 0,
            None if vol_cm3 is None else round(vol_cm3, 4),
            0,
            "cm3",
            ">",
        ),
        Finding(
            "overhang_area",
            True,
            round(overhang_area_mm2(mesh, overhang_deg), 1),
            None,
            "mm2",
            f"> {overhang_deg:g} deg",
            "info",
        ),
        Finding(
            "degenerate_faces", True, int((mesh.area_faces < 1e-12).sum()), 0, op="==", severity="warning"
        ),
        Finding(
            "triangles",
            len(mesh.faces) <= MAX_TRIANGLES,
            len(mesh.faces),
            MAX_TRIANGLES,
            op="<=",
            severity="warning",
        ),
        Finding(
            "xy_centred", centre <= CENTRE_TOL_MM, round(centre, 3), CENTRE_TOL_MM, "mm", "<=", "warning"
        ),
    ]
    if brep_volume_cm3 is not None and vol_cm3 is not None:
        dev = abs(vol_cm3 - brep_volume_cm3) / brep_volume_cm3 * 100
        findings.append(
            Finding("volume_vs_brep", dev <= VOLUME_TOL_PCT, round(dev, 5), VOLUME_TOL_PCT, "%", "<=")
        )
    if build_volume is not None:
        fits = all(e <= b for e, b in zip(ext, build_volume, strict=True))
        findings.append(
            Finding("build_volume", fits, [round(float(e), 2) for e in ext], build_volume, "mm", "<=")
        )
    return MeshReport(
        str(path), [round(float(e), 3) for e in ext], None if vol_cm3 is None else round(vol_cm3, 4), findings
    )


def render(report: MeshReport) -> str:
    e = report.extents_mm
    lines = [
        f"{Path(report.file).name}: {e[0]:.2f} x {e[1]:.2f} x {e[2]:.2f} mm, volume {report.volume_cm3} cm3"
    ]
    for f in report.findings:
        mark = "ok  " if f.ok else ("FAIL" if f.severity == "error" else "warn")
        value = f"{f.value} {f.unit}".rstrip()
        limit = "" if f.limit is None else f" (limit {f.op} {f.limit})".replace("  ", " ")
        lines.append(f"  {mark} {f.code}: {value}{limit}")
    lines.append("  OK" if report.ok else "  FAILED")
    return "\n".join(lines)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--overhang", type=float, default=50.0, help="overhang limit in degrees from vertical")
    ap.add_argument("--brep-volume-cm3", type=float, help="CAD body volume to compare against (single file)")
    ap.add_argument("--build-volume", help="printer build volume X,Y,Z in mm, e.g. 256,256,256")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    ap.add_argument("--report", help="append the text results to this file")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        bv = [float(v) for v in args.build_volume.split(",")] if args.build_volume else None
        if bv is not None and len(bv) != 3:
            raise ValueError("--build-volume needs three values X,Y,Z")
        reports = [check(f, args.overhang, args.brep_volume_cm3, bv) for f in args.files]
    except Exception as err:  # unreadable input is a usage error, not a geometry failure
        print(f"usage error: {err}", file=sys.stderr)
        return 2
    text = "\n".join(render(r) for r in reports)
    if args.json:
        print(json.dumps([{**asdict(r), "ok": r.ok} for r in reports], indent=1))
    else:
        print(text)
    if args.report:
        with Path(args.report).open("a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
