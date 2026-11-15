import json

import pytest
from conftest import load_script

ca = load_script("geometry-verification/scripts/check_assembly.py")


def block(lo, hi):
    from build123d import Box, Pos

    size = [b - a for a, b in zip(lo, hi, strict=True)]
    centre = [(a + b) / 2 for a, b in zip(lo, hi, strict=True)]
    return Pos(*centre) * Box(*size)


@pytest.fixture(scope="module")
def scene(tmp_path_factory):
    """A rail channel holding a slider, an obstacle, and two plates with a straight or offset gap."""
    from build123d import export_stl

    out = tmp_path_factory.mktemp("assembly")
    shapes = {
        "channel": block((-50, 0, 0), (50, 20, 2))
        + block((-50, 0, 2), (50, 2, 10))
        + block((-50, 18, 2), (50, 20, 10))
        + block((-50, 2, 8), (50, 4, 10))
        + block((-50, 16, 8), (50, 18, 10)),
        "open_channel": block((-50, 0, 0), (50, 20, 2)),
        "slider": block((-10, 2.2, 2.2), (10, 17.8, 7.8)),
        "obstacle": block((30, 5, 2), (32, 15, 6)),
        "plate_low": block((0, 0, 0), (2, 20, 4.9)),
        "plate_high": block((0, 0, 5.1), (2, 20, 10)),
        "plate_offset": block((3, 0, 4.8), (5, 20, 10)),
    }
    for name, shape in shapes.items():
        export_stl(shape, str(out / f"{name}.stl"), tolerance=0.01)
    return out


def run(scene, checks, capsys=None, datums=None):
    path = scene / "assembly.json"
    names = ["channel", "open_channel", "slider", "obstacle", "plate_low", "plate_high", "plate_offset"]
    path.write_text(
        json.dumps({"parts": {n: f"{n}.stl" for n in names}, "datums": datums or {}, "checks": checks})
    )
    code = ca.main([str(path), "--json"])
    return code, (json.loads(capsys.readouterr().out) if capsys else None)


def test_interference_at_rest_and_planted_pose(scene):
    ok = {"interference": [{"parts": ["channel", "slider"]}]}
    assert run(scene, ok)[0] == 0
    sunk = {"interference": [{"parts": ["channel", "slider"], "pose": {"slider": [0, 0, -0.5]}}]}
    assert run(scene, sunk)[0] == 1


def test_slide_path_catches_obstacle(scene):
    path = {"moving": "slider", "fixed": ["channel"], "to": [35, 0, 0], "step": 1}
    assert run(scene, {"slide_path": [path]})[0] == 0
    assert run(scene, {"slide_path": [{**path, "fixed": ["channel", "obstacle"]}]})[0] == 1


def test_held_needs_the_rail(scene):
    lift = {"moving": "slider", "fixed": ["channel"], "by": [0, 0, 1], "min_mm3": 1}
    assert run(scene, {"held": [lift]})[0] == 0
    assert run(scene, {"held": [{**lift, "fixed": ["open_channel"]}]})[0] == 1
    above_rail = {"region": [[-50, 0, 10], [50, 20, 20]]}
    assert run(scene, {"held": [{**lift, **above_rail}]})[0] == 1


def test_line_of_sight_straight_gap_leaks_offset_gap_does_not(scene, capsys):
    sight = {"axis": "x", "range": [-1, 6], "window": [[0, 0], [20, 10]], "step": 0.1}
    code, out = run(scene, {"line_of_sight": [{**sight, "parts": ["plate_low", "plate_high"]}]}, capsys)
    assert code == 1
    value = out["results"][0]["value"]
    assert value["open_mm2"] == pytest.approx(4.0, abs=0.05)
    assert value["open_bounds"][0][1] > 4.8
    assert value["open_bounds"][1][1] < 5.2
    labyrinth = {**sight, "parts": ["plate_low", "plate_offset"]}
    assert run(scene, {"line_of_sight": [labyrinth]})[0] == 0


def test_upward_faces_finds_floor_shelf(scene):
    near_floor = {"part": "channel", "box": [[-40, 3, 1], [40, 17, 3]]}
    assert run(scene, {"upward_faces": [near_floor]})[0] == 1
    mid_air = {"part": "channel", "box": [[-40, 5, 4], [40, 15, 7]]}
    assert run(scene, {"upward_faces": [mid_air]})[0] == 0


def test_not_checked_and_usage_errors(scene):
    assert run(scene, {})[0] == 3
    assert run(scene, {"typo": []})[0] == 2
    assert run(scene, {"interference": [{"parts": ["channel", "missing"]}]})[0] == 2
    assert (
        run(
            scene,
            {
                "held": [
                    {
                        "moving": "slider",
                        "fixed": ["channel"],
                        "by": [0, 0, 1],
                        "region": [[0, 0, 0], [0, 1, 1]],
                    }
                ]
            },
        )[0]
        == 2
    )


def test_datums_in_assembly_checks(scene):
    lift = {
        "moving": "slider",
        "fixed": ["channel"],
        "by": [0, 0, 1],
        "region": [[-50, 0, "rail_z"], [50, 20, "rail_z + 2"]],
    }
    assert run(scene, {"held": [lift]}, datums={"rail_z": 8})[0] == 0
    assert run(scene, {"held": [lift]}, datums={"rail_z": 12})[0] == 1
