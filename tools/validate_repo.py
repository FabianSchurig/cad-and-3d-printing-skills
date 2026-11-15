"""Repository invariants that no single file can enforce on its own.

Run:  uv run tools/validate_repo.py [--root .]

Checks
  skills     SKILL.md frontmatter (Agent Skills spec + VS Code limits), body size, relative links
  scripts    PEP 723 header present, module-level imports declared, deps mirrored in the `cad`
             dependency group, CLI contract (main() + documented exit codes)
  plugin     plugin.json / mcp.json follow Agent Plugins 1.0; marketplace entry matches
  versions   pyproject == plugin.json == marketplace entry, and CHANGELOG has that version
  mcp        .vscode/mcp.json and the plugin mcp.json register the same servers
  docs       README lists every skill
  tracked    no CAD/print/scan artefacts or personal absolute paths in git-tracked files

Exit codes: 0 all invariants hold, 1 violations found.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path

import yaml

PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
MCP_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")
SKILL_KEYS = {
    "name",
    "description",
    "argument-hint",
    "user-invocable",
    "disable-model-invocation",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
    "context",
}
PLUGIN_KEYS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
MAX_DESCRIPTION = 1024
MAX_BODY_LINES = 500
# Always-loaded context budget: sum of descriptions of model-invocable skills.
MAX_MODEL_DESCRIPTIONS = 6000
# import name -> distribution name, where they differ
IMPORT_TO_DIST = {"cv2": "opencv-python-headless", "PIL": "pillow", "potrace": "potracer", "yaml": "pyyaml"}
FORBIDDEN_TRACKED = re.compile(r"\.(stl|3mf|step|stp|f3d|f3z|obj|gcode|bgcode|zip|pdf|npy|jpe?g|webp)$", re.I)
PERSONAL_PATH = re.compile(r"(/home/(?!<user>)[a-z_][\w-]*/|[A-Z]:\\\\?Users\\\\?(?!<)\w|/Users/(?!<)\w)")
LINK_RE = re.compile(r"\]\((?!https?://|#|mailto:)([^)\s]+)\)")

Check = Callable[[Path], list[str]]


def frontmatter(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not match:
        raise ValueError("missing YAML frontmatter")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data, match.group(2)


def skill_dirs(root: Path) -> list[Path]:
    return sorted(p for p in (root / ".github" / "skills").iterdir() if p.is_dir())


def _check_frontmatter(where: Path, meta: dict[str, object]) -> list[str]:
    errors = []
    name, desc = meta.get("name"), meta.get("description")
    if name != where.parent.name:
        errors.append(f"{where}: name {name!r} must equal directory name {where.parent.name!r}")
    if not isinstance(name, str) or not NAME_RE.match(name) or len(name) > 64:
        errors.append(f"{where}: name must be lowercase-hyphenated, <= 64 chars")
    if not isinstance(desc, str) or not desc.strip():
        errors.append(f"{where}: description is required")
    elif len(desc) > MAX_DESCRIPTION:
        errors.append(f"{where}: description {len(desc)} > {MAX_DESCRIPTION} chars")
    elif not meta.get("disable-model-invocation") and "use when" not in desc.lower():
        errors.append(f"{where}: model-invocable description needs a 'Use when ...' trigger")
    unknown = set(meta) - SKILL_KEYS
    if unknown:
        errors.append(f"{where}: unknown frontmatter keys {sorted(unknown)}")
    return errors


def _check_body(md: Path, where: Path, body: str) -> list[str]:
    errors = []
    lines = body.count("\n")
    if lines > MAX_BODY_LINES:
        errors.append(f"{where}: body {lines} lines > {MAX_BODY_LINES}; move detail to references/")
    for target in LINK_RE.findall(body):
        if not (md.parent / target.split("#")[0]).exists():
            errors.append(f"{where}: broken relative link {target}")
    return errors


def check_skills(root: Path) -> list[str]:
    errors: list[str] = []
    model_desc_chars = 0
    for d in skill_dirs(root):
        md = d / "SKILL.md"
        if not md.is_file():
            errors.append(f"{d.relative_to(root)}: missing SKILL.md")
            continue
        where = md.relative_to(root)
        try:
            meta, body = frontmatter(md)
        except (ValueError, yaml.YAMLError) as err:
            errors.append(f"{where}: {err}")
            continue
        errors += _check_frontmatter(where, meta) + _check_body(md, where, body)
        desc = meta.get("description")
        if isinstance(desc, str) and not meta.get("disable-model-invocation"):
            model_desc_chars += len(desc)
    if model_desc_chars > MAX_MODEL_DESCRIPTIONS:
        errors.append(
            f"model-invocable skill descriptions total {model_desc_chars} chars "
            f"> {MAX_MODEL_DESCRIPTIONS} (always-loaded context budget)"
        )
    return errors


def pep723(source: str) -> dict[str, object] | None:
    match = re.search(r"^# /// script\n((?:#.*\n)+?)# ///$", source, re.M)
    if not match:
        return None
    toml = "".join(
        line[2:] if line.startswith("# ") else line[1:] for line in match.group(1).splitlines(True)
    )
    return tomllib.loads(toml)


def dist_name(requirement: str) -> str:
    return re.split(r"[<>=!~\[; ]", requirement, maxsplit=1)[0].lower().replace("_", "-")


def module_imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:  # module level only: lazy imports are optional dependencies
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names - set(sys.stdlib_module_names) - {"__future__"}


def check_scripts(root: Path) -> list[str]:
    errors: list[str] = []
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    cad_group = {dist_name(r) for r in project["dependency-groups"]["cad"] if isinstance(r, str)}
    declared_anywhere: set[str] = set()
    for script in sorted((root / ".github" / "skills").glob("*/scripts/*.py")):
        where = script.relative_to(root)
        source = script.read_text(encoding="utf-8")
        meta = pep723(source)
        if meta is None:
            errors.append(f"{where}: missing PEP 723 '# /// script' header")
            continue
        deps = meta.get("dependencies", [])
        declared = {dist_name(d) for d in deps} if isinstance(deps, list) else set()
        declared_anywhere |= declared
        for imp in sorted(module_imports(ast.parse(source))):
            if IMPORT_TO_DIST.get(imp, imp).lower() not in declared:
                errors.append(f"{where}: imports {imp!r} but does not declare it in its PEP 723 header")
        for dep in sorted(declared - cad_group):
            errors.append(f"{where}: dependency {dep!r} missing from pyproject [dependency-groups].cad")
        if "def main(" not in source or "sys.exit(main())" not in source:
            errors.append(f"{where}: CLI contract needs main(argv) -> int and sys.exit(main())")
        if "Exit codes:" not in source:
            errors.append(f"{where}: module docstring must document 'Exit codes:'")
    lazy_only = {"build123d"}  # optional, loaded lazily for STEP input; still tested via the cad group
    for dep in sorted(cad_group - declared_anywhere - lazy_only):
        errors.append(f"pyproject cad group lists {dep!r} but no skill script declares it")
    return errors


def as_dicts(value: object) -> list[dict[str, object]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def load_json(path: Path, errors: list[str]) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        errors.append(f"{path.name}: {err}")
        return {}
    return data if isinstance(data, dict) else {}


def _versions(root: Path, errors: list[str]) -> dict[str, object]:
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    plugin = load_json(root / ".github" / "plugin.json", errors)
    market = load_json(root / ".github" / "plugin" / "marketplace.json", errors)
    entries = [p for p in as_dicts(market.get("plugins")) if p.get("name") == plugin.get("name")]
    return {
        "pyproject": project["version"],
        "plugin.json": plugin.get("version"),
        "marketplace": entries[0].get("version") if entries else None,
    }


def check_plugin(root: Path) -> list[str]:
    errors: list[str] = []
    gh = root / ".github"
    plugin = load_json(gh / "plugin.json", errors)
    if plugin.get("$schema") != PLUGIN_SCHEMA:
        errors.append(f"plugin.json: $schema must be {PLUGIN_SCHEMA}")
    name = plugin.get("name")
    if not isinstance(name, str) or not PLUGIN_NAME_RE.match(name) or "--" in name or ".." in name:
        errors.append("plugin.json: invalid plugin name")
    if set(plugin) - PLUGIN_KEYS:
        errors.append(f"plugin.json: unknown keys {sorted(set(plugin) - PLUGIN_KEYS)}")
    mcp = load_json(gh / "mcp.json", errors)
    if mcp.get("$schema") != MCP_SCHEMA or set(mcp) != {"$schema", "mcpServers"}:
        errors.append(f"mcp.json: needs exactly $schema ({MCP_SCHEMA}) and mcpServers")
    market = load_json(gh / "plugin" / "marketplace.json", errors)
    entries = [p for p in as_dicts(market.get("plugins")) if p.get("name") == name]
    if len(entries) != 1:
        errors.append(f"marketplace.json: needs exactly one entry for plugin {name!r}")
    elif not (root / str(entries[0].get("source", "")).removeprefix("./") / "plugin.json").is_file():
        errors.append("marketplace.json: plugin source does not point at the directory holding plugin.json")
    return errors


def check_versions(root: Path) -> list[str]:
    errors: list[str] = []
    versions = _versions(root, errors)
    if len(set(versions.values())) != 1:
        errors.append(f"version mismatch: {versions}")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## [{versions['pyproject']}]" not in changelog:
        errors.append(f"CHANGELOG.md has no '## [{versions['pyproject']}]' section")
    return errors


def check_mcp(root: Path) -> list[str]:
    errors: list[str] = []
    workspace = load_json(root / ".vscode" / "mcp.json", errors).get("servers", {})
    plugin = load_json(root / ".github" / "mcp.json", errors).get("mcpServers", {})
    if not isinstance(workspace, dict) or not isinstance(plugin, dict):
        return [*errors, "mcp configs must contain server mappings"]
    for name in sorted(set(workspace) | set(plugin)):
        w, p = workspace.get(name, {}), plugin.get(name, {})
        if w.get("url") != p.get("url"):
            errors.append(f"MCP server {name!r}: .vscode/mcp.json and .github/mcp.json disagree ({w} vs {p})")
    return errors


def check_docs(root: Path) -> list[str]:
    readme = (root / "README.md").read_text(encoding="utf-8")
    return [
        f"README.md does not mention skill {d.name!r}"
        for d in skill_dirs(root)
        if f"`{d.name}`" not in readme
    ]


def tracked_files(root: Path) -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [root / f for f in out.decode().split("\0") if f]


def check_tracked(root: Path) -> list[str]:
    errors: list[str] = []
    for f in tracked_files(root):
        rel = f.relative_to(root).as_posix()
        if FORBIDDEN_TRACKED.search(rel):
            errors.append(f"{rel}: CAD/print/scan artefacts must not be tracked (designs stay private)")
        elif f.suffix in {".md", ".py", ".json", ".toml", ".yml", ".yaml", ".txt"} and f.is_file():
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if PERSONAL_PATH.search(line):
                    errors.append(f"{rel}:{i}: personal absolute path; use a placeholder like <user>")
    return errors


CHECKS: dict[str, Check] = {
    "skills": check_skills,
    "scripts": check_scripts,
    "plugin": check_plugin,
    "versions": check_versions,
    "mcp": check_mcp,
    "docs": check_docs,
    "tracked": check_tracked,
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=Path(__file__).resolve().parents[1], type=Path)
    args = ap.parse_args(argv)
    failed = 0
    for name, check in CHECKS.items():
        errors = check(args.root)
        print(f"{'ok  ' if not errors else 'FAIL'} {name}")
        for e in errors:
            print(f"     {e}")
        failed += len(errors)
    print("OK" if not failed else f"FAILED: {failed} violation(s)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
