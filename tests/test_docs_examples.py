"""Code shown in skills must work: run the build123d example and parse the checks.json example."""

import json
import re
import subprocess
import sys

from conftest import SKILLS, load_script

cp = load_script("geometry-verification/scripts/check_part.py")


def fenced(skill: str, lang: str) -> str:
    text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.search(rf"```{lang}\n(.*?)```", text, re.S)
    assert match, f"{skill}: no ```{lang} block"
    return match.group(1)


def test_build123d_example_builds_and_exports(tmp_path):
    model = tmp_path / "model" / "model.py"
    model.parent.mkdir()
    model.write_text(fenced("build123d-modeling", "python"))
    run = subprocess.run([sys.executable, str(model)], capture_output=True, text=True, check=False)
    assert run.returncode == 0, run.stderr
    assert (tmp_path / "out" / "part.stl").stat().st_size > 0
    assert (tmp_path / "out" / "part.step").stat().st_size > 0


def test_checks_json_example_uses_known_checks():
    example = json.loads(fenced("geometry-verification", "json"))
    assert set(example["checks"]) <= set(cp.CHECKS)
