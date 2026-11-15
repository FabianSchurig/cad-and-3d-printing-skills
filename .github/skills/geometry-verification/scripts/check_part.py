# /// script
# requires-python = ">=3.11"
# dependencies = ["trimesh>=4.0", "numpy>=1.26", "scipy>=1.11", "networkx>=3.0", "rtree>=1.0"]
# ///
"""Verify a part against the acceptance checks of its spec (red/green, like a test suite).

Usage:
    uv run check_part.py checks.json [part.stl|part.3mf|part.step] [--json]
    (STEP input: uv run --with build123d check_part.py ...)

checks.json (all checks optional; lengths in mm, points in model coordinates):
{
  "file": "out/part.stl",                         # default part, relative to checks.json
  "datums": {"z_top": 10},                        # optional named spec values (see below)
  "checks": {
    "bodies": 1,
    "watertight": true,
    "extents": {"x": [39.9, 40.1], "y": [19.9, 20.1], "z": [9.9, 10.1]},
    "volume_mm3": [7000, 8000],
    "material_at": [{"at": [10, 0, 5], "why": "solid flank"}],
    "empty_at":    [{"at": [0, 0, 5], "why": "M3 clearance bore"}],
    "min_wall": {"mm": 0.9, "max_thin_fraction": 0.002}
  }
}

Write expected values from the spec / caliper measurements BEFORE modelling, never by reading
them back from the model. min_wall samples surface points, casts a ray inward and measures the
distance to the opposite-facing wall; it cannot see features thinner than the mesh resolution and
ignores hits on non-opposing faces (inside corners).

Datums: any number inside "checks" may be a string expression over the datums, e.g.
{"at": [0, 0, "z_top - 2.5"]}. Name datums after spec rows so moving a feature means editing one
datum instead of every probe. Only + - * / and parentheses are allowed.

Exit codes: 0 all checks pass, 1 a check failed, 2 usage error, 3 nothing was checked.
"""

from __future__ import annotations

import argparse
import ast
import json
import operator
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

STEP_SUFFIXES = (".step", ".stp")


@dataclass(frozen=True)
class Result:
    code: str
    ok: bool
    value: Any
    expected: Any
    why: str = ""


def load_trimesh(path: str | Path) -> trimesh.Trimesh:
    """Load a file as one triangle mesh; reject anything else (empty scenes, point clouds)."""
    mesh = trimesh.load(path, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{path}: not a triangle mesh")
    return mesh


def load_mesh(path: Path) -> trimesh.Trimesh:
    if path.suffix.lower() not in STEP_SUFFIXES:
        return load_trimesh(path)
    try:
        from build123d import export_stl, import_step
    except ImportError as err:
        raise RuntimeError("STEP input needs build123d: uv run --with build123d check_part.py ...") from err
    with tempfile.TemporaryDirectory() as tmp:
        stl = Path(tmp) / "part.stl"
        export_stl(import_step(str(path)), str(stl), tolerance=0.01, angular_tolerance=0.1)
        return load_trimesh(stl)


def wall_thickness(mesh: trimesh.Trimesh, samples: int = 4000, seed: int = 0) -> np.ndarray:
    """Distances from sampled surface points to the opposing wall along the inward normal."""
    pts, face_idx = trimesh.sample.sample_surface(mesh, samples, seed=seed)
    normals = mesh.face_normals[face_idx]
    hits, ray_idx, tri = mesh.ray.intersects_location(pts - normals * 1e-4, -normals, multiple_hits=False)
    opposing = np.einsum("ij,ij->i", mesh.face_normals[tri], normals[ray_idx]) < -0.5
    return np.linalg.norm(hits[opposing] - pts[ray_idx[opposing]], axis=1)


def _check_bodies(mesh: trimesh.Trimesh, want: int) -> list[Result]:
    n = len(mesh.split(only_watertight=False))
    return [Result("bodies", n == want, n, want)]


def _check_watertight(mesh: trimesh.Trimesh, want: bool) -> list[Result]:
    return [Result("watertight", mesh.is_watertight == want, mesh.is_watertight, want)]


def _check_extents(mesh: trimesh.Trimesh, want: dict[str, list[float]]) -> list[Result]:
    ext = mesh.bounds[1] - mesh.bounds[0]
    out = []
    for axis, (lo, hi) in want.items():
        v = round(float(ext["xyz".index(axis)]), 4)
        out.append(Result(f"extent_{axis}", lo <= v <= hi, v, [lo, hi]))
    return out


def _check_volume(mesh: trimesh.Trimesh, want: list[float]) -> list[Result]:
    v = round(float(mesh.volume), 2) if mesh.is_watertight else None
    return [Result("volume_mm3", v is not None and want[0] <= v <= want[1], v, want)]


def _probes(
    code: str, want_material: bool
) -> Callable[[trimesh.Trimesh, list[dict[str, Any]]], list[Result]]:
    def run(mesh: trimesh.Trimesh, probes: list[dict[str, Any]]) -> list[Result]:
        inside = mesh.contains(np.array([p["at"] for p in probes], float))
        label = {True: "material", False: "empty"}
        return [
            Result(
                code,
                bool(got) == want_material,
                label[bool(got)],
                label[want_material],
                f"{p.get('why', '')} @ {p['at']}".strip(),
            )
            for p, got in zip(probes, inside, strict=True)
        ]

    return run


def _check_min_wall(mesh: trimesh.Trimesh, want: dict[str, float]) -> list[Result]:
    limit, frac_max = want["mm"], want.get("max_thin_fraction", 0.002)
    t = wall_thickness(mesh)
    frac = float((t < limit).mean()) if len(t) else 1.0
    p1 = round(float(np.percentile(t, 1)), 3) if len(t) else None
    return [
        Result(
            "min_wall",
            frac <= frac_max,
            {"thin_fraction": round(frac, 4), "p1_mm": p1},
            {"mm": limit, "max_thin_fraction": frac_max},
        )
    ]


_OPS: dict[type, Callable[..., float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def evaluate(expr: str, datums: dict[str, float]) -> float:
    """Evaluate an arithmetic expression over named datums (no calls, no attributes)."""

    def ev(node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in datums:
                raise ValueError(f"unknown datum {node.id!r} in {expr!r}; known: {sorted(datums)}")
            return float(datums[node.id])
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError(f"unsupported expression {expr!r}")

    return ev(ast.parse(expr, mode="eval").body)


def resolve(value: Any, datums: dict[str, float], key: str = "") -> Any:
    """Replace datum expressions in numeric positions; 'why' texts stay as written."""
    if isinstance(value, dict):
        return {k: resolve(v, datums, k) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, datums, key) for v in value]
    if isinstance(value, str) and key != "why":
        return round(evaluate(value, datums), 6)
    return value


CHECKS: dict[str, Callable[[trimesh.Trimesh, Any], list[Result]]] = {
    "bodies": _check_bodies,
    "watertight": _check_watertight,
    "extents": _check_extents,
    "volume_mm3": _check_volume,
    "material_at": _probes("material_at", want_material=True),
    "empty_at": _probes("empty_at", want_material=False),
    "min_wall": _check_min_wall,
}


def run_checks(checks: dict[str, Any], mesh: trimesh.Trimesh) -> list[Result]:
    unknown = set(checks) - set(CHECKS)
    if unknown:
        raise ValueError(f"unknown checks {sorted(unknown)}; known: {sorted(CHECKS)}")
    return [
        r
        for key, fn in CHECKS.items()
        if checks.get(key) not in (None, [], {})
        for r in fn(mesh, checks[key])
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("checks")
    ap.add_argument("part", nargs="?")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    spec_path = Path(args.checks)
    try:
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        part = Path(args.part) if args.part else spec_path.parent / spec["file"]
        checks = resolve(spec.get("checks", {}), spec.get("datums", {}))
        results = run_checks(checks, load_mesh(part))
    except Exception as err:
        print(f"usage error: {err}", file=sys.stderr)
        return 2
    if not results:
        print("NOT CHECKED: no checks defined")
        return 3
    failed = sum(not r.ok for r in results)
    if args.json:
        print(
            json.dumps(
                {"part": str(part), "ok": not failed, "results": [asdict(r) for r in results]}, indent=1
            )
        )
    else:
        for r in results:
            print(
                f"{'ok  ' if r.ok else 'FAIL'} {r.code}: {r.value} (expected {r.expected}) {r.why}".rstrip()
            )
        print("OK" if not failed else f"FAILED ({failed} of {len(results)})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
