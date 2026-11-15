import math

from conftest import load_script

cm = load_script("print-export-validation/scripts/check_mesh.py")


def failed(report):
    return {f.code for f in report.findings if not f.ok}


def test_good_part_passes(parts):
    report = cm.check(parts["plate"], build_volume=[256, 256, 256])
    assert report.ok, cm.render(report)
    assert math.isclose(report.volume_cm3, (8000 - math.pi * 1.6**2 * 10) / 1000, rel_tol=1e-3)


def test_each_planted_defect_is_reported(parts):
    assert "watertight" in failed(cm.check(parts["open"]))
    assert "bodies" in failed(cm.check(parts["two"]))
    assert "on_bed" in failed(cm.check(parts["floating"]))
    assert "build_volume" in failed(cm.check(parts["plate"], build_volume=[30, 30, 30]))
    assert "volume_vs_brep" in failed(cm.check(parts["plate"], brep_volume_cm3=9.0))


def test_overhang_counts_flat_ceiling_not_bed(parts):
    # the M3 bore has no downward faces; a box floating above the bed has a 100 mm2 underside
    assert cm.overhang_area_mm2(cm.trimesh.load(parts["plate"]), 50) == 0
    assert math.isclose(cm.overhang_area_mm2(cm.trimesh.load(parts["floating"]), 50), 0, abs_tol=1e-6)


def test_cli_exit_codes_and_outputs(parts, tmp_path, capsys):
    report = tmp_path / "report.txt"
    assert cm.main([str(parts["plate"]), "--report", str(report)]) == 0
    assert "OK" in report.read_text()
    assert cm.main([str(parts["two"]), "--json"]) == 1
    assert '"ok": false' in capsys.readouterr().out
    bad = tmp_path / "bad.stl"
    bad.write_text("not a mesh")
    assert cm.main([str(bad)]) == 2
    assert cm.main([str(parts["plate"]), "--build-volume", "1,2"]) == 2


def test_brep_volume_tolerance_on_small_part(tmp_path):
    from build123d import Box, Pos, export_stl

    stl = tmp_path / "small.stl"
    export_stl(Pos(0, 0, 4) * Box(12.5, 5, 8), str(stl))  # exactly 500 mm3
    report = cm.check(stl, brep_volume_cm3=0.5)
    assert report.ok, cm.render(report)
    assert not cm.check(stl, brep_volume_cm3=0.5002).ok  # 0.04 % off
