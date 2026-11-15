## What and why

<!-- One paragraph. Link the issue. -->

## Checklist

- [ ] `uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest && uv run tools/validate_repo.py` passes
- [ ] New or changed checks/scripts have a test with a planted defect that fails without the change
- [ ] Skill descriptions say what the skill does and "Use when ..."; SKILL.md stays short, details in `references/`
- [ ] No designs, measurements, personal paths or CAD/print files are included
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
