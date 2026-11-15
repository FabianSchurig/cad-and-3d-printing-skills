"""Each repository invariant is seen to fail on a planted violation, and the real repo passes."""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import load_tool

vr = load_tool("validate_repo.py")

SKILL = """---
name: demo-skill
description: Demo skill. Use when testing the validator.
---
See [the script](scripts/run.py).
"""
SCRIPT = '''# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=1.26"]
# ///
"""Demo. Exit codes: 0 OK."""
import sys

import numpy


def main() -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def make_repo(root: Path) -> Path:
    gh = root / ".github"
    (gh / "skills" / "demo-skill" / "scripts").mkdir(parents=True)
    (gh / "plugin").mkdir()
    (root / ".vscode").mkdir()
    (gh / "skills" / "demo-skill" / "SKILL.md").write_text(SKILL)
    (gh / "skills" / "demo-skill" / "scripts" / "run.py").write_text(SCRIPT)
    (gh / "plugin.json").write_text(
        json.dumps({"$schema": vr.PLUGIN_SCHEMA, "name": "demo", "version": "1.0.0"})
    )
    (gh / "mcp.json").write_text(
        json.dumps(
            {
                "$schema": vr.MCP_SCHEMA,
                "mcpServers": {"cad": {"type": "streamable-http", "url": "http://127.0.0.1:1/mcp"}},
            }
        )
    )
    (gh / "plugin" / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "m",
                "owner": {"name": "o"},
                "plugins": [{"name": "demo", "source": ".github", "version": "1.0.0"}],
            }
        )
    )
    (root / ".vscode" / "mcp.json").write_text(
        json.dumps({"servers": {"cad": {"type": "http", "url": "http://127.0.0.1:1/mcp"}}})
    )
    (root / "pyproject.toml").write_text(
        '[project]\nversion = "1.0.0"\n[dependency-groups]\ncad = ["numpy>=1.26"]\n'
    )
    (root / "CHANGELOG.md").write_text("## [1.0.0]\n")
    (root / "README.md").write_text("`demo-skill`\n")
    return root


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path)


def edit(path: Path, old: str, new: str) -> None:
    path.write_text(path.read_text().replace(old, new))


def test_valid_repo_passes(repo):
    for check in vr.CHECKS.values():
        assert check(repo) == []
    assert vr.main(["--root", str(repo)]) == 0


@pytest.mark.parametrize(
    ("check", "plant"),
    [
        (
            "skills",
            lambda r: edit(r / ".github/skills/demo-skill/SKILL.md", "name: demo-skill", "name: Demo"),
        ),
        (
            "skills",
            lambda r: edit(r / ".github/skills/demo-skill/SKILL.md", "Use when testing", "For testing"),
        ),
        (
            "skills",
            lambda r: edit(r / ".github/skills/demo-skill/SKILL.md", "---\nSee", "colour: red\n---\nSee"),
        ),
        (
            "skills",
            lambda r: edit(r / ".github/skills/demo-skill/SKILL.md", "scripts/run.py", "scripts/gone.py"),
        ),
        ("skills", lambda r: edit(r / ".github/skills/demo-skill/SKILL.md", "See", "line\n" * 501)),
        ("skills", lambda r: (r / ".github/skills/demo-skill/SKILL.md").write_text("no frontmatter")),
        (
            "scripts",
            lambda r: edit(r / ".github/skills/demo-skill/scripts/run.py", "import numpy", "import scipy"),
        ),
        (
            "scripts",
            lambda r: edit(r / ".github/skills/demo-skill/scripts/run.py", "# /// script", "# script"),
        ),
        ("scripts", lambda r: edit(r / ".github/skills/demo-skill/scripts/run.py", "Exit codes", "Exits")),
        ("scripts", lambda r: edit(r / "pyproject.toml", 'cad = ["numpy>=1.26"]', 'cad = ["numpy", "vtk"]')),
        ("plugin", lambda r: edit(r / ".github/plugin.json", '"name": "demo"', '"name": "Demo--x"')),
        ("plugin", lambda r: edit(r / ".github/mcp.json", '"$schema"', '"extra": 1, "$schema"')),
        (
            "plugin",
            lambda r: edit(r / ".github/plugin/marketplace.json", '"source": ".github"', '"source": "nope"'),
        ),
        ("versions", lambda r: edit(r / "pyproject.toml", '"1.0.0"', '"1.1.0"')),
        ("versions", lambda r: edit(r / "CHANGELOG.md", "1.0.0", "0.9.0")),
        ("mcp", lambda r: edit(r / ".vscode/mcp.json", "127.0.0.1:1", "127.0.0.1:2")),
        ("docs", lambda r: edit(r / "README.md", "`demo-skill`", "")),
    ],
)
def test_planted_violation_is_reported(repo, check, plant):
    plant(repo)
    assert vr.CHECKS[check](repo), f"{check} did not report the planted violation"
    assert vr.main(["--root", str(repo)]) == 1


def test_tracked_artefacts_and_personal_paths(repo):
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "part.stl").write_text("solid x")
    (repo / "notes.md").write_text("see /" + "home/alice/designs/x\n")  # split so this file stays clean
    (repo / "ok.md").write_text("see /home/<user>/designs/x\n")
    subprocess.run(["git", "add", "part.stl", "notes.md", "ok.md"], cwd=repo, check=True)
    errors = vr.check_tracked(repo)
    assert any("part.stl" in e for e in errors) and any("notes.md:1" in e for e in errors)
    assert not any("ok.md" in e for e in errors)


def test_real_repository_passes():
    assert vr.main([]) == 0
