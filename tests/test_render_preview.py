import numpy as np
from conftest import load_script
from PIL import Image

rp = load_script("geometry-verification/scripts/render_preview.py")


def test_renders_offscreen(parts, tmp_path):
    assert rp.main([str(parts["plate"]), "--views", "iso,top", "-o", str(tmp_path)]) == 0
    for view in ("iso", "top"):
        img = np.asarray(Image.open(tmp_path / f"plate_{view}.png").convert("L"))
        assert img.std() > 10, f"{view} preview is blank"


def test_step_input(tmp_path):
    from build123d import Box, export_step

    step = tmp_path / "box.step"
    export_step(Box(10, 10, 10), str(step))
    assert rp.main([str(step), "--views", "iso", "-o", str(tmp_path)]) == 0
    assert (tmp_path / "box_iso.png").exists()


def test_usage_errors(parts, tmp_path):
    assert rp.main([str(parts["plate"]), "--views", "diagonal", "-o", str(tmp_path)]) == 2
    other = tmp_path / "x.dxf"
    other.write_text("")
    assert rp.main([str(other), "-o", str(tmp_path)]) == 2
