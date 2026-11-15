# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html): a skill rename, removal or
breaking script CLI change is a major bump; new skills or script options are minor.

## [Unreleased]

## [0.2.0]

Lessons from a multi-session Fusion redesign (sliding lid, labyrinth seals, slicer project update).

### Added

- `check_assembly.py` (`geometry-verification`): interference, slide paths, held directions,
  line-of-sight leaks through seams and upward dust shelves between mating parts, each in a chosen pose.
- `datums` in `check_part.py` and `check_assembly.py`: probe coordinates may be expressions over
  named spec values, so moving a feature edits one number.
- `place_on_bed.py` and `update_3mf_project.py` (`print-export-validation`): orient and place print
  meshes, and swap meshes in an existing Bambu Studio / OrcaSlicer project while keeping its presets.
- References: Fusion snippets (design inventory, reading the user's selection, fully constrained
  polyline sketches, export and save), CLI slicing incl. Windows slicers from WSL, `progress.md` template.

### Changed

- `cad-workflow` change-part playbook: retire the old version (orphan bodies, sketches, parameters)
  as its own step; distrust new checks that are already green on the old design.
- `cad-review`: no leftovers, fully constrained sketches, single-face surfaces, assembly checks in poses.
- `fusion-api-scripting` / `fusion-parametric-modeling`: collapse timeline groups before deleting,
  rollback on error, loader sets `__name__`, save policy, fully constrained sketches, retiring features.
- `fdm-design-rules`: closures, lids and dust seals (positive locks, labyrinths, no inner ledges).
- `cad-spec`: Frames section in the spec template, datums for shared probe coordinates.

## [0.1.0]

### Added

- Spec-first CAD workflow: `cad-workflow` router, `cad-spec`, `cad-review` and `cad-handoff` skills.
- Modelling skills for Autodesk Fusion (`fusion-api-scripting`, `fusion-parametric-modeling`) and
  headless code-CAD (`build123d-modeling`).
- Verification-first `geometry-verification` with `check_part.py` and `render_preview.py`.
- `print-export-validation` with `check_mesh.py`; `fdm-design-rules`; `print-failure-diagnosis`.
- `scan-to-sketch` (`scan_to_outline.py`) and `mesh-surface-detail` (`vector_relief.py`).
- Agent Plugins 1.0 packaging with a Copilot CLI marketplace, devcontainer, uv project,
  CI workflows and repository invariant checks.
