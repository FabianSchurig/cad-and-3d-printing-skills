# /// script
# requires-python = ">=3.11"
# dependencies = ["trimesh>=4.0", "numpy>=1.26", "manifold3d>=3.0", "rtree>=1.0", "scipy>=1.11"]
# ///
"""Check how mating parts fit together: interference, slide paths, held directions, line-of-sight
leaks through gaps and dust shelves - each at one or more poses of the moving parts.

Usage:
    uv run check_assembly.py assembly.json [--json]

assembly.json (lengths in mm, all parts in ONE shared frame; paths relative to the JSON file):
{
  "parts": {"bin": "out/bin.stl", "lid": "out/lid.stl"},
  "datums": {"z_top": 118.9},                       # optional, as in check_part.py
  "checks": {
    "interference": [{"parts": ["bin", "lid"], "max_mm3": 0.01, "pose": {"lid": [0, 0, 0.3]}}],
    "slide_path":   [{"moving": "lid", "fixed": ["bin"], "to": [-240, 0, 0], "step": 2, "max_mm3": 0.01}],
    "held":         [{"moving": "lid", "fixed": ["bin"], "by": [0, 0, 1], "min_mm3": 1,
                      "region": [[-100, -1, 100], [0, 8, 130]], "why": "rail holds the lid down"}],
    "line_of_sight": [{"parts": ["bin", "lid"], "axis": "x", "range": [-123, -115],
                       "window": [[2, 90], [73.5, 116]], "step": 0.1, "max_mm2": 0.05,
                       "why": "no straight path for dust through the end closure"}],
    "upward_faces": [{"part": "bin", "box": [[-117, 2, 100], [70, 73, 114]], "max_mm2": 1.0,
                      "min_normal_z": 0.9, "why": "no ledges inside where dust settles"}]
  }
}

- pose: translation per part, applied before the check. List a check several times with different
  poses (closed, partly open, lifted by the play) - a moving part checked only at rest proves little.
- interference: overlap volume of every pair in `parts`, optionally only inside `region`.
- slide_path: moves `moving` from its pose to pose+`to` in `step` mm increments; the worst overlap
  with `fixed` along the path must stay <= max_mm3.
- held: moving `moving` by `by` must collide (overlap >= min_mm3, optionally inside `region`).
  Proves a lid, latch or rail actually blocks that direction.
- line_of_sight: rays parallel to `axis` through a grid over `window` (the two other axes in xyz
  order) from range[0] to range[1]; any ray that misses all material is an open straight path.
  Reports the open area (rays x step^2). Only axis-parallel lines are tested.
- upward_faces: area of faces whose normal z > min_normal_z with centres inside `box`.
- datums: any number may be a string expression over the datums ("z_top - 3"); only + - * / ().

Exit codes: 0 all checks pass, 1 a check failed, 2 usage error, 3 nothing was checked.
"""

from __future__ import annotations

import argparse
import ast
import json
import operator
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import trimesh

Parts = dict[str, trimesh.Trimesh]
Box = tuple[np.ndarray, np.ndarray]


@dataclass(frozen=True)
class Result:
    code: str
    ok: bool
    value: Any
    expected: Any
    why: str = ""


def load_trimesh(path: str | Path) -> trimesh.Trimesh:
    mesh = trimesh.load(path, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError(f"{path}: not a triangle mesh")
    return mesh


def as_box(value: Any) -> Box | None:
    if value is None:
        return None
    lo, hi = np.asarray(value[0], float), np.asarray(value[1], float)
    if lo.shape != (3,) or hi.shape != (3,) or (hi <= lo).any():
        raise ValueError(f"box must be [[x0, y0, z0], [x1, y1, z1]] with x1 > x0 etc., got {value}")
    return lo, hi


def posed(parts: Parts, pose: dict[str, list[float]] | None) -> Parts:
    out = dict(parts)
    for name, d in (pose or {}).items():
        if name not in parts:
            raise ValueError(f"pose names unknown part {name!r}")
        out[name] = parts[name].copy()
        out[name].apply_translation(np.asarray(d, float))
    return out


def overlap_mm3(a: trimesh.Trimesh, b: trimesh.Trimesh, region: Box | None = None) -> float:
    """Volume of a ∩ b (∩ region), 0 if the bounding boxes do not even touch."""
    lo, hi = np.maximum(a.bounds[0], b.bounds[0]), np.minimum(a.bounds[1], b.bounds[1])
    if region is not None:
        lo, hi = np.maximum(lo, region[0]), np.minimum(hi, region[1])
    if (hi <= lo).any():
        return 0.0
    meshes = [a, b]
    if region is not None:
        meshes.append(trimesh.creation.box(bounds=np.array(region)))
    inter = trimesh.boolean.intersection(meshes, engine="manifold")
    return 0.0 if inter.is_empty else round(abs(float(inter.volume)), 4)


def _names(parts: Parts, names: list[str]) -> list[str]:
    unknown = [n for n in names if n not in parts]
    if unknown:
        raise ValueError(f"unknown parts {unknown}; known: {sorted(parts)}")
    return names


def _why(spec: dict[str, Any]) -> str:
    pose = f" pose {spec['pose']}" if spec.get("pose") else ""
    return f"{spec.get('why', '')}{pose}".strip()


def check_interference(parts: Parts, spec: dict[str, Any]) -> Result:
    p = posed(parts, spec.get("pose"))
    region = as_box(spec.get("region"))
    names = _names(p, spec["parts"])
    vols = {f"{a}/{b}": overlap_mm3(p[a], p[b], region) for a, b in combinations(names, 2)}
    limit = spec.get("max_mm3", 0.01)
    return Result("interference", all(v <= limit for v in vols.values()), vols, f"<= {limit}", _why(spec))


def check_slide_path(parts: Parts, spec: dict[str, Any]) -> Result:
    p = posed(parts, spec.get("pose"))
    moving, fixed = _names(p, [spec["moving"]])[0], _names(p, spec["fixed"])
    to = np.asarray(spec["to"], float)
    n = max(1, int(np.ceil(np.linalg.norm(to) / spec.get("step", 1.0))))
    worst, at = 0.0, 0.0
    for t in np.linspace(0.0, 1.0, n + 1):
        m = p[moving].copy()
        m.apply_translation(to * t)
        v = sum(overlap_mm3(m, p[f]) for f in fixed)
        if v > worst:
            worst, at = v, float(t)
    limit = spec.get("max_mm3", 0.01)
    value = {"worst_mm3": round(worst, 4), "at": [round(float(x), 3) for x in to * at]}
    return Result("slide_path", worst <= limit, value, f"<= {limit}", _why(spec))


def check_held(parts: Parts, spec: dict[str, Any]) -> Result:
    p = posed(parts, spec.get("pose"))
    moving, fixed = _names(p, [spec["moving"]])[0], _names(p, spec["fixed"])
    m = p[moving].copy()
    m.apply_translation(np.asarray(spec["by"], float))
    region = as_box(spec.get("region"))
    v = round(sum(overlap_mm3(m, p[f], region) for f in fixed), 4)
    limit = spec.get("min_mm3", 1.0)
    return Result("held", v >= limit, v, f">= {limit}", _why(spec))


def open_rays(
    meshes: list[trimesh.Trimesh],
    axis: int,
    rng: tuple[float, float],
    w_lo: tuple[float, float],
    w_hi: tuple[float, float],
    *,
    step: float,
) -> np.ndarray:
    """Grid points (other two axes, window w_lo..w_hi) whose axis-parallel line over rng misses every mesh."""
    other = [i for i in range(3) if i != axis]
    lo, hi = np.zeros(3), np.zeros(3)
    lo[axis], hi[axis] = rng
    lo[other], hi[other] = w_lo, w_hi
    clip = trimesh.creation.box(bounds=np.array([lo, hi]))
    u = np.arange(w_lo[0] + step / 2, w_hi[0], step)
    v = np.arange(w_lo[1] + step / 2, w_hi[1], step)
    uu, vv = (g.ravel() for g in np.meshgrid(u, v))
    blocked = np.zeros(len(uu), bool)
    origins = np.zeros((len(uu), 3))
    origins[:, other[0]], origins[:, other[1]] = uu, vv
    origins[:, axis] = rng[0] - 1.0
    direction = np.zeros(3)
    direction[axis] = 1.0
    for mesh in meshes:
        inside = trimesh.boolean.intersection([mesh, clip], engine="manifold")
        if inside.is_empty:
            continue
        hits = inside.ray.intersects_any(origins, np.tile(direction, (len(origins), 1)))
        blocked |= hits
    return np.stack([uu[~blocked], vv[~blocked]], axis=1)


def check_line_of_sight(parts: Parts, spec: dict[str, Any]) -> Result:
    p = posed(parts, spec.get("pose"))
    axis = "xyz".index(spec["axis"])
    step = float(spec.get("step", 0.1))
    (u0, v0), (u1, v1) = spec["window"]
    r0, r1 = spec["range"]
    meshes = [p[n] for n in _names(p, spec["parts"])]
    free = open_rays(meshes, axis, (r0, r1), (u0, v0), (u1, v1), step=step)
    area = round(len(free) * step * step, 4)
    limit = spec.get("max_mm2", 0.05)
    value: dict[str, Any] = {"open_mm2": area}
    if len(free):
        value["open_bounds"] = [
            [round(float(x), 2) for x in free.min(0)],
            [round(float(x), 2) for x in free.max(0)],
        ]
    return Result("line_of_sight", area <= limit, value, f"<= {limit}", _why(spec))


def check_upward_faces(parts: Parts, spec: dict[str, Any]) -> Result:
    mesh = posed(parts, spec.get("pose"))[_names(parts, [spec["part"]])[0]]
    box = as_box(spec["box"])
    assert box is not None
    c = mesh.triangles_center
    sel = (mesh.face_normals[:, 2] > spec.get("min_normal_z", 0.9)) & np.all(
        (c > box[0]) & (c < box[1]), axis=1
    )
    area = round(float(mesh.area_faces[sel].sum()), 3)
    value: dict[str, Any] = {"area_mm2": area}
    if sel.any():
        value["z"] = [round(float(c[sel, 2].min()), 2), round(float(c[sel, 2].max()), 2)]
    limit = spec.get("max_mm2", 1.0)
    return Result("upward_faces", area <= limit, value, f"<= {limit}", _why(spec))


NAME_KEYS = {"why", "axis", "parts", "part", "moving", "fixed"}
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
    """Replace datum expressions in numeric positions; part names, axes and 'why' stay as written."""
    if isinstance(value, dict):
        return {k: resolve(v, datums, k) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve(v, datums, key) for v in value]
    if isinstance(value, str) and key not in NAME_KEYS:
        return round(evaluate(value, datums), 6)
    return value


CHECKS: dict[str, Callable[[Parts, dict[str, Any]], Result]] = {
    "interference": check_interference,
    "slide_path": check_slide_path,
    "held": check_held,
    "line_of_sight": check_line_of_sight,
    "upward_faces": check_upward_faces,
}


def run_checks(checks: dict[str, list[dict[str, Any]]], parts: Parts) -> list[Result]:
    unknown = set(checks) - set(CHECKS)
    if unknown:
        raise ValueError(f"unknown checks {sorted(unknown)}; known: {sorted(CHECKS)}")
    return [CHECKS[key](parts, spec) for key in CHECKS for spec in checks.get(key) or []]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("assembly")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    path = Path(args.assembly)
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
        parts = {name: load_trimesh(path.parent / f) for name, f in spec["parts"].items()}
        results = run_checks(resolve(spec.get("checks", {}), spec.get("datums", {})), parts)
    except Exception as err:
        print(f"usage error: {err}", file=sys.stderr)
        return 2
    if not results:
        print("NOT CHECKED: no checks defined")
        return 3
    failed = sum(not r.ok for r in results)
    if args.json:
        print(json.dumps({"ok": not failed, "results": [asdict(r) for r in results]}, indent=1))
    else:
        for r in results:
            print(
                f"{'ok  ' if r.ok else 'FAIL'} {r.code}: {r.value} (expected {r.expected}) {r.why}".rstrip()
            )
        print("OK" if not failed else f"FAILED ({failed} of {len(results)})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
