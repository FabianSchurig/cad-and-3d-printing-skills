import json

import cv2
import numpy as np
import pytest
from conftest import load_script

so = load_script("scan-to-sketch/scripts/scan_to_outline.py")
DPI = 200
PX_PER_MM = DPI / 25.4


def synthetic_scan(path, stretch_y=1.0):
    """80 x 50 mm dark plate with a 10 mm hole on white, at 200 dpi (optionally stretched in Y)."""
    sy = PX_PER_MM * stretch_y
    img = np.full((int(70 * sy), int(100 * PX_PER_MM)), 235, np.uint8)
    x0, y0 = int(10 * PX_PER_MM), int(10 * sy)
    x1, y1 = x0 + round(80 * PX_PER_MM), y0 + round(50 * sy)
    cv2.rectangle(img, (x0, y0), (x1 - 1, y1 - 1), 40, -1)
    cv2.ellipse(
        img,
        (x0 + round(60 * PX_PER_MM), y0 + round(25 * sy)),
        (round(5 * PX_PER_MM), round(5 * sy)),
        0,
        0,
        360,
        235,
        -1,
    )
    cv2.imwrite(str(path), img)
    return x0, y0, x1, y1


def run(tmp_path, *args):
    img = tmp_path / "scan.png"
    return img, so.main([str(img), *args, "-o", str(tmp_path)])


def manifest(tmp_path):
    return json.loads((tmp_path / "scan_outline.json").read_text())


def test_calibrated_outline_and_circle(tmp_path):
    x0, y0, x1, _ = synthetic_scan(tmp_path / "scan.png")
    _, code = run(tmp_path, "--calib", f"{x0},{y0},{x1},{y0},80")
    assert code == 0
    m = manifest(tmp_path)
    assert m["scale_state"] == "calibrated"
    assert m["outer_extent_mm"] == pytest.approx([80, 50], abs=0.3)
    holes = [s for s in m["shapes"] if s["hole"] and s["kind"] == "circle"]
    assert len(holes) == 1 and holes[0]["circle"]["d"] == pytest.approx(10, abs=0.3)
    for suffix in ("_outline.dxf", "_outline.svg", "_overlay.png"):
        assert (tmp_path / f"scan{suffix}").stat().st_size > 0


def test_per_axis_calibration_corrects_transport_stretch(tmp_path):
    x0, y0, x1, y1 = synthetic_scan(tmp_path / "scan.png", stretch_y=1.02)
    _, code = run(tmp_path, "--calib", f"{x0},{y0},{x1},{y0},80", "--calib", f"{x0},{y0},{x0},{y1},50")
    assert code == 0
    m = manifest(tmp_path)
    assert m["scale_state"] == "calibrated_per_axis"
    assert m["outer_extent_mm"] == pytest.approx([80, 50], abs=0.3)


def test_dpi_only_is_flagged_nominal(tmp_path):
    synthetic_scan(tmp_path / "scan.png")
    _, code = run(tmp_path, "--dpi", str(DPI), "--mirror")
    assert code == 0
    m = manifest(tmp_path)
    assert m["scale_state"] == "nominal" and m["warnings"] and m["mirrored"]


def test_failures(tmp_path):
    synthetic_scan(tmp_path / "scan.png")
    assert run(tmp_path)[1] == 2  # no scale
    assert run(tmp_path, "--calib", "1,1,1,1,10")[1] == 2  # degenerate calibration
    blank = tmp_path / "blank.png"
    cv2.imwrite(str(blank), np.full((100, 100), 200, np.uint8))
    assert so.main([str(blank), "--dpi", "200", "-o", str(tmp_path)]) == 1
