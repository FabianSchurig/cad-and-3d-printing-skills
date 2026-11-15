import zipfile

import numpy as np
import pytest
import trimesh
from conftest import load_script

pb = load_script("print-export-validation/scripts/place_on_bed.py")
up = load_script("print-export-validation/scripts/update_3mf_project.py")

ROOT = """<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" \
xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">
 <resources>
  <object id="2" type="model">
   <components>
    <component p:path="/3D/Objects/object_1.model" objectid="1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>
   </components>
  </object>
 </resources>
 <build>
  <item objectid="2" transform="0 1 0 -1 0 0 0 0 1 128 140 5" printable="1"/>
 </build>
</model>
"""
SETTINGS = """<?xml version="1.0" encoding="UTF-8"?>
<config>
  <object id="2">
    <metadata key="name" value="Lid"/>
    <metadata face_count="12"/>
  </object>
</config>
"""
PRESETS = b'{"layer_height": "0.2", "filament_type": ["PETG"]}'


def sub_model(mesh):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<model unit="millimeter" '
        'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n <resources>\n'
        '  <object id="1" type="model">\n   '
        + up.mesh_xml(mesh)
        + "\n  </object>\n </resources>\n <build/>\n</model>\n"
    )


@pytest.fixture
def project(tmp_path):
    path = tmp_path / "old.3mf"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("3D/3dmodel.model", ROOT)
        z.writestr("3D/Objects/object_1.model", sub_model(trimesh.creation.box((10, 10, 10))))
        z.writestr("Metadata/model_settings.config", SETTINGS)
        z.writestr("Metadata/project_settings.config", PRESETS)
        z.writestr("Metadata/plate_1.gcode", "; stale toolpath")
    return path


def test_place_on_bed_flips_and_centres(tmp_path):
    lid = trimesh.creation.box(bounds=[[10, 10, 50], [30, 20, 52]])  # plate on top
    lid = trimesh.util.concatenate(
        [lid, trimesh.creation.box(bounds=[[15, 12, 45], [25, 18, 50]])]
    )  # boss below
    src, dst = tmp_path / "lid.stl", tmp_path / "lid_print.stl"
    lid.export(src)
    assert pb.main([str(src), str(dst), "--rotate", "x:180"]) == 0
    placed = trimesh.load(dst)
    assert placed.bounds[0][2] == pytest.approx(0, abs=1e-6)
    assert placed.bounds.mean(axis=0)[:2] == pytest.approx([0, 0], abs=1e-6)
    bed = placed.vertices[:, 2] < 1e-6
    assert np.ptp(placed.vertices[bed][:, 0]) == pytest.approx(20)  # the plate, not the boss, is on the bed
    assert pb.main([str(src), str(dst), "--rotate", "q:90"]) == 2


def test_replace_keeps_presets_places_on_bed_and_drops_gcode(project, tmp_path, capsys):
    new_mesh = trimesh.creation.box(bounds=[[0, 0, 0], [40, 20, 8]])
    stl, out = tmp_path / "lid.stl", tmp_path / "new.3mf"
    new_mesh.export(stl)
    assert up.main([str(project), str(out), "--replace", f"Lid={stl}"]) == 0
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert z.read("Metadata/project_settings.config") == PRESETS
        root = z.read("3D/3dmodel.model").decode()
        sub = z.read("3D/Objects/object_1.model").decode()
        cfg = z.read("Metadata/model_settings.config").decode()
    assert "Metadata/plate_1.gcode" not in names
    assert sub.count("<vertex ") == len(new_mesh.vertices)
    assert 'transform="0 1 0 -1 0 0 0 0 1 128 140 4"' in root  # xy and rotation kept, z = half height
    assert f'face_count="{len(new_mesh.faces)}"' in cfg
    assert "dropped stale G-code" in capsys.readouterr().out


def test_list_and_usage_errors(project, tmp_path, capsys):
    assert up.main([str(project), "--list"]) == 0
    assert "Lid" in capsys.readouterr().out
    stl = tmp_path / "x.stl"
    trimesh.creation.box((1, 1, 1)).export(stl)
    assert up.main([str(project), str(tmp_path / "n.3mf"), "--replace", f"Missing={stl}"]) == 2
    assert up.main([str(project), str(tmp_path / "n.3mf")]) == 2
    assert up.main([str(project), str(tmp_path / "n.3mf"), "--replace", "Lid"]) == 2
