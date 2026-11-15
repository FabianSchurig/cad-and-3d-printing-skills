# /// script
# requires-python = ">=3.11"
# dependencies = ["trimesh>=4.0", "numpy>=1.26"]
# ///
"""Swap meshes inside an existing Bambu Studio / OrcaSlicer project 3MF and keep everything else:
printer, filament and process presets, per-object settings, plates and object positions.

Usage:
    uv run update_3mf_project.py old.3mf new.3mf --replace "Part name=out/print/part.stl" [...]
    uv run update_3mf_project.py old.3mf --list

The object is found by its name in Metadata/model_settings.config (as shown in the slicer's object
list) or by the 3MF object's name attribute. The new mesh should already be in print orientation
(see place_on_bed.py); it is centred on its bounding box like the slicer stores meshes, and the build
item keeps its xy position and rotation while its z is reset so the part sits on the bed. Embedded
G-code from an earlier slice is dropped: a toolpath of the old geometry must never be reused.
Re-slice and check the result (thumbnails stay stale until the slicer saves the project again).

Exit codes: 0 written, 1 written but a replaced mesh did not read back, 2 usage error.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
import trimesh

MODEL = "3D/3dmodel.model"
SETTINGS = "Metadata/model_settings.config"
STALE = re.compile(r"^Metadata/plate_\d+\.gcode(\.md5)?$")


def object_names(files: dict[str, bytes]) -> dict[str, str]:
    """Object name -> top-level object id, from model_settings.config and name attributes."""
    names: dict[str, str] = {}
    root = files[MODEL].decode()
    for oid, name in re.findall(r'<object id="(\d+)"[^>]*?\bname="([^"]*)"', root):
        names[name] = oid
    if SETTINGS in files:
        for oid, body in re.findall(r'<object id="(\d+)">(.*?)</object>', files[SETTINGS].decode(), re.S):
            m = re.search(r'<metadata key="name" value="([^"]*)"/>', body)
            if m:
                names[m.group(1)] = oid
    return names


def mesh_xml(mesh: trimesh.Trimesh) -> str:
    v = "\n".join(f'     <vertex x="{x:.7g}" y="{y:.7g}" z="{z:.7g}"/>' for x, y, z in mesh.vertices)
    t = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in mesh.faces)
    return f"<mesh>\n    <vertices>\n{v}\n    </vertices>\n    <triangles>\n{t}\n    </triangles>\n   </mesh>"


def object_block(text: str, oid: str) -> re.Match[str]:
    m = re.search(rf'<object id="{oid}"[^>]*>.*?</object>', text, re.S)
    if not m:
        raise ValueError(f"object id {oid} not found")
    return m


def mesh_location(files: dict[str, bytes], oid: str) -> tuple[str, str]:
    """(file, object id) holding the mesh of top-level object oid; follows a single component."""
    block = object_block(files[MODEL].decode(), oid).group(0)
    if "<mesh>" in block:
        return MODEL, oid
    comps = re.findall(r"<component\b[^>]*/>", block)
    if len(comps) != 1:
        raise ValueError(f"object {oid} has {len(comps)} components; only single-mesh objects are supported")
    path = re.search(r'p:path="/?([^"]+)"', comps[0])
    sub = re.search(r'objectid="(\d+)"', comps[0])
    if not sub:
        raise ValueError(f"object {oid}: component without objectid")
    return (path.group(1) if path else MODEL), sub.group(1)


def item_transform(root: str, oid: str) -> tuple[re.Match[str], np.ndarray]:
    item = re.search(rf'<item objectid="{oid}"[^>]*/>', root)
    if not item:
        raise ValueError(f"object {oid} is not placed on any plate (no build item)")
    t = re.search(r'transform="([^"]+)"', item.group(0))
    values = (
        np.array(t.group(1).split(), float) if t else np.array([1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0], float)
    )
    return item, values


def replace(files: dict[str, bytes], name: str, mesh: trimesh.Trimesh) -> None:
    names = object_names(files)
    if name not in names:
        raise ValueError(f"no object named {name!r}; objects: {sorted(names)}")
    oid = names[name]
    m = mesh.copy()
    m.apply_translation(-m.bounds.mean(axis=0))

    path, mesh_id = mesh_location(files, oid)
    text = files[path].decode()
    block = object_block(text, mesh_id)
    new_block = re.sub(r"<mesh>.*?</mesh>", lambda _: mesh_xml(m), block.group(0), count=1, flags=re.S)
    files[path] = (text[: block.start()] + new_block + text[block.end() :]).encode()

    root = files[MODEL].decode()
    item, t = item_transform(root, oid)
    rot = t[:9].reshape(3, 3)  # 3MF row-vector convention: p' = p @ rot + t
    t[11] = -float((m.vertices @ rot)[:, 2].min())
    new_t = " ".join(f"{x:.9g}" for x in t)
    if 'transform="' in item.group(0):
        new_item = re.sub(r'transform="[^"]*"', f'transform="{new_t}"', item.group(0))
    else:
        new_item = item.group(0).replace("/>", f' transform="{new_t}"/>')
    files[MODEL] = (root[: item.start()] + new_item + root[item.end() :]).encode()

    if SETTINGS in files:
        cfg = files[SETTINGS].decode()
        obj = re.search(rf'<object id="{oid}">.*?</object>', cfg, re.S)
        if obj:
            fixed = re.sub(r'face_count="\d+"', f'face_count="{len(m.faces)}"', obj.group(0))
            files[SETTINGS] = (cfg[: obj.start()] + fixed + cfg[obj.end() :]).encode()


def read_back(path: Path, name: str) -> int:
    with zipfile.ZipFile(path) as z:
        files = {n: z.read(n) for n in z.namelist()}
    file, mesh_id = mesh_location(files, object_names(files)[name])
    return len(re.findall(r"<vertex ", object_block(files[file].decode(), mesh_id).group(0)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst", nargs="?")
    ap.add_argument("--replace", action="append", default=[], metavar="NAME=MESH")
    ap.add_argument("--list", action="store_true", help="list object names and exit")
    args = ap.parse_args(argv)
    try:
        with zipfile.ZipFile(args.src) as z:
            infos = z.infolist()
            files = {i.filename: z.read(i.filename) for i in infos}
        if args.list:
            for name, oid in sorted(object_names(files).items()):
                print(f"{oid:>4}  {name}")
            return 0
        if not args.dst or not args.replace:
            raise ValueError("need dst and at least one --replace NAME=MESH (or --list)")
        expected = {}
        for spec in args.replace:
            name, sep, mesh_path = spec.rpartition("=")
            if not sep or not name:
                raise ValueError(f"--replace {spec!r} must be NAME=MESH")
            mesh = trimesh.load(mesh_path, force="mesh")
            if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
                raise ValueError(f"{mesh_path}: not a triangle mesh")
            replace(files, name, mesh)
            expected[name] = len(mesh.vertices)
    except Exception as err:
        print(f"usage error: {err}", file=sys.stderr)
        return 2
    dropped = [n for n in files if STALE.match(n)]
    with zipfile.ZipFile(args.dst, "w", zipfile.ZIP_DEFLATED) as z:
        for info in infos:
            if info.filename not in dropped:
                z.writestr(info, files[info.filename], compress_type=zipfile.ZIP_DEFLATED)
    bad = [n for n, count in expected.items() if read_back(Path(args.dst), n) != count]
    for name, count in expected.items():
        print(f"{'FAIL' if name in bad else 'ok  '} {name}: {count} vertices")
    if dropped:
        print(f"dropped stale G-code: {', '.join(dropped)}")
    print(f"wrote {args.dst}" if not bad else f"FAILED: {len(bad)} mesh(es) did not read back")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
