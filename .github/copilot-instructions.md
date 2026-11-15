# Copilot instructions – CAD & 3D-printing workspace

This repository is a reusable agent setup for designing parts for FDM 3D printing: agent skills (`.github/skills/`), an Agent Plugin manifest (`.github/plugin.json`), MCP config and the Python tooling that tests them. It can double as a CAD workspace: each design lives in its own top-level folder, and the allow-list `.gitignore` keeps those folders untracked.

## Privacy

- Never commit designs, models, scans, photos or print files. Never loosen the `.gitignore` allow-list or use `git add -f`.
- Tracked content stays generic: no specific designs, measurements or personal paths. `tools/validate_repo.py` enforces this.

## Working on designs

- Start CAD tasks with `/cad-workflow`; it routes to a playbook and the right skills. Spec and acceptance checks come before modelling; a part is done when checks on the exported geometry pass.
- Two CAD back ends: **Autodesk Fusion** through its MCP server (`autodesk-fusion`, `http://127.0.0.1:27182/mcp`; Fusion runs on Windows, so paths it opens come from `wslpath -w`) and **build123d** code-CAD that runs headless. Fusion API scripts (`adsk.*`) run only inside Fusion; everything else runs with `uv run`. Never mix the two in one file.
- Each design folder is self-contained (`spec.md`, `checks.json`, `assembly.json`, `progress.md`, `model/`, `out/`) and keeps the language it already uses. Reply to the user in the language they write in.
- Read the design's `progress.md` first and keep its Commands, Frames and Gotchas sections current; that is how the next session avoids rediscovering them.
- When the user points out a defect, add the check that would have caught it before fixing the model. A redesign is finished only when the old version is gone: no orphan bodies, sketches or parameters, every sketch fully constrained, no seams on faces it touched.
- Save the Fusion document only when the user asks. After that, save after each verified change, with a message saying what changed.
- Never send a job to a printer unless asked. Keep "slice checked" apart from "physically tested".
- Design-folder scripts are untracked and not part of the repository gate. Keep them ruff-clean where you touch them, but do not block on old findings in them.

## Working on this repository

- Python ≥ 3.11, managed with uv. Setup: `uv sync`. Gate before every commit:
  `uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest && uv run tools/validate_repo.py`
- Single test: `uv run pytest tests/test_check_mesh.py::test_good_part_passes`.
- Skill scripts are standalone CLIs with a PEP 723 header (`uv run <script> --help`), typed pure functions, `main(argv) -> int` and the shared exit codes 0 OK, 1 FAILED, 2 usage error, 3 not checked. Skills never import each other.
- Every check or script gets a test with a planted defect that the check must catch. Fix the design or the code, never weaken a check to pass.
- Release: bump the version in `pyproject.toml`, `.github/plugin.json` and `.github/plugin/marketplace.json`, add a `CHANGELOG.md` section, tag `vX.Y.Z`. See `CONTRIBUTING.md`.
