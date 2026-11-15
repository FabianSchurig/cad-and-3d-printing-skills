"""Shared fixtures: load skill scripts by path and build reference parts with planted defects."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".github" / "skills"


def _load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


def load_script(rel: str) -> ModuleType:
    """Import a skill script (skills are not a package; scripts must stay standalone)."""
    return _load(SKILLS / rel)


def load_tool(name: str) -> ModuleType:
    return _load(ROOT / "tools" / name)


@pytest.fixture(scope="session")
def parts(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Reference parts built with build123d: one good part and several planted defects."""
    import trimesh
    from build123d import Box, Cylinder, Pos, export_stl

    out = tmp_path_factory.mktemp("parts")
    shapes = {
        "plate": Pos(0, 0, 5) * Box(40, 20, 10) - Pos(0, 0, 5) * Cylinder(1.6, 10),  # 40x20x10, M3 bore
        "thin": Pos(0, 0, 5) * Box(40, 20, 10) + Pos(0, 0, 15) * Box(30, 0.5, 10),  # 0.5 mm fin
        "two": Pos(0, 0, 5) * Box(10, 10, 10) + Pos(30, 0, 5) * Box(10, 10, 10),
        "floating": Pos(0, 0, 8) * Box(10, 10, 10),
    }
    files = {}
    for name, shape in shapes.items():
        files[name] = out / f"{name}.stl"
        export_stl(shape, str(files[name]), tolerance=0.01)

    mesh = trimesh.load_mesh(files["plate"])
    assert isinstance(mesh, trimesh.Trimesh)
    mesh.update_faces(list(range(len(mesh.faces) - 2)))  # delete two faces: not watertight
    files["open"] = out / "open.stl"
    mesh.export(files["open"])
    return files
