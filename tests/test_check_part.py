import json

import pytest
from conftest import load_script

cp = load_script("geometry-verification/scripts/check_part.py")

PLATE = {
    "bodies": 1,
    "watertight": True,
    "extents": {"x": [39.9, 40.1], "y": [19.9, 20.1], "z": [9.9, 10.1]},
    "volume_mm3": [7880, 7960],
    "material_at": [{"at": [10, 0, 5], "why": "solid flank"}],
    "empty_at": [{"at": [0, 0, 5], "why": "M3 bore"}],
    "min_wall": {"mm": 0.9},
}


def write(tmp_path, checks, **extra):
    path = tmp_path / "checks.json"
    path.write_text(json.dumps({"checks": checks, **extra}))
    return str(path)


def test_spec_passes(parts, tmp_path):
    assert cp.main([write(tmp_path, PLATE), str(parts["plate"])]) == 0


def test_default_file_from_checks_json(parts, tmp_path, capsys):
    assert cp.main([write(tmp_path, PLATE, file=str(parts["plate"])), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


@pytest.mark.parametrize(
    "broken",
    [
        {"extents": {"x": [50, 51]}},
        {"volume_mm3": [1, 2]},
        {"empty_at": [{"at": [10, 0, 5], "why": "planted: this is material"}]},
        {"material_at": [{"at": [0, 0, 5], "why": "planted: this is the bore"}]},
        {"bodies": 2},
        {"watertight": False},
    ],
)
def test_each_check_can_fail(parts, tmp_path, broken):
    assert cp.main([write(tmp_path, broken), str(parts["plate"])]) == 1


def test_min_wall_detects_thin_fin(parts, tmp_path):
    checks = write(tmp_path, {"min_wall": {"mm": 0.9}})
    assert cp.main([checks, str(parts["plate"])]) == 0
    assert cp.main([checks, str(parts["thin"])]) == 1


def test_not_checked_and_usage_errors(parts, tmp_path):
    assert cp.main([write(tmp_path, {}), str(parts["plate"])]) == 3
    assert cp.main([write(tmp_path, PLATE), str(tmp_path / "missing.stl")]) == 2
    assert cp.main([write(tmp_path, {"typo_check": 1}), str(parts["plate"])]) == 2


def test_step_input(parts, tmp_path):
    from build123d import Box, Pos, export_step

    step = tmp_path / "plate.step"
    export_step(Pos(0, 0, 5) * Box(40, 20, 10), str(step))
    assert cp.main([write(tmp_path, {"extents": PLATE["extents"]}), str(step)]) == 0


def test_datums_move_probes_with_one_edit(parts, tmp_path):
    probes = {
        "material_at": [{"at": [10, 0, "z_top - 5"], "why": "D1 - flank"}],
        "extents": {"z": ["z_top - 0.1", "z_top + 0.1"]},
    }
    assert cp.main([write(tmp_path, probes, datums={"z_top": 10}), str(parts["plate"])]) == 0
    assert cp.main([write(tmp_path, probes, datums={"z_top": 20}), str(parts["plate"])]) == 1


@pytest.mark.parametrize("expr", ["missing + 1", "__import__('os')", "z_top ** 2"])
def test_datum_expressions_are_restricted(parts, tmp_path, expr):
    checks = {"material_at": [{"at": [10, 0, expr]}]}
    assert cp.main([write(tmp_path, checks, datums={"z_top": 10}), str(parts["plate"])]) == 2
