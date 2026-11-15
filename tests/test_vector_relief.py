import math

import manifold3d as m3d
import numpy as np
import trimesh
from conftest import load_script
from PIL import Image, ImageDraw

vr = load_script("mesh-surface-detail/scripts/vector_relief.py")
SURFACE = ["--surface-z", "0,60", "--surface-r", "30,30", "--art-z", "10,50"]


def artwork(path, thin_line_px=None):
    """400 x 200 px image with a 100 px disk (= 20 mm at 40 mm artwork height)."""
    img = Image.new("L", (400, 200), 255)
    draw = ImageDraw.Draw(img)
    draw.ellipse((150, 50, 250, 150), fill=0)
    if thin_line_px:
        draw.line((20, 20, 380, 20), fill=0, width=thin_line_px)
    img.save(path)


def tube(path):
    profile = m3d.CrossSection([np.array([[27.0, 0], [30, 0], [30, 60], [27, 60]])])
    vr.to_trimesh(m3d.Manifold.revolve(profile, 256)).export(path)


def test_relief_unions_onto_tube_watertight(tmp_path, capsys):
    art, body, out = tmp_path / "a.png", tmp_path / "tube.stl", tmp_path / "out.stl"
    artwork(art)
    tube(body)
    assert vr.main([str(art), *SURFACE, "--union", str(body), "-o", str(out)]) == 0
    merged, base = trimesh.load(out), trimesh.load(body)
    assert merged.is_watertight and len(merged.split()) == 1
    disk_area = math.pi * 10**2
    assert 0.8 * disk_area < merged.volume - base.volume < 1.2 * disk_area  # 1 mm proud
    assert "WARNING" not in capsys.readouterr().out


def test_relief_sits_on_cone_at_requested_angle(tmp_path):
    art, out = tmp_path / "a.png", tmp_path / "relief.stl"
    artwork(art)
    assert (
        vr.main(
            [
                str(art),
                "--surface-z",
                "0,60",
                "--surface-r",
                "30,24",
                "--art-z",
                "10,50",
                "--angle",
                "90",
                "-o",
                str(out),
            ]
        )
        == 0
    )
    relief = trimesh.load(out)
    assert relief.is_watertight
    centre = relief.bounds.mean(axis=0)
    assert centre[1] > 20 and abs(centre[0]) < 1  # centred on +Y
    r = np.hypot(relief.vertices[:, 0], relief.vertices[:, 1])
    cone_r = 30 + relief.vertices[:, 2] * (24 - 30) / 60
    assert (r - cone_r).min() > -0.41 and (r - cone_r).max() < 1.01  # within sink/height band


def test_thin_stroke_warning(tmp_path, capsys):
    art = tmp_path / "a.png"
    artwork(art, thin_line_px=1)  # 1 px = 0.2 mm
    assert vr.main([str(art), *SURFACE, "-o", str(tmp_path / "r.stl")]) == 0
    assert "WARNING" in capsys.readouterr().out


def test_usage_errors(tmp_path):
    art = tmp_path / "a.png"
    artwork(art)
    assert vr.main([str(art), "--surface-z", "0,60", "--surface-r", "30,30", "--art-z", "50,70"]) == 2
    assert vr.main([str(art), *SURFACE, "--span-deg", "400"]) == 2
    Image.new("L", (10, 10), 255).save(tmp_path / "blank.png")
    assert vr.main([str(tmp_path / "blank.png"), *SURFACE]) == 2
