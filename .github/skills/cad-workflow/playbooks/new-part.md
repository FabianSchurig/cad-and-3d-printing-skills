# Playbook: new part

1. Spec: use the `cad-spec` skill to write `spec.md` and `checks.json`. Done when the user has confirmed the requirements, the dimensions table and the out-of-scope list.
2. Process rules: read `fdm-design-rules` and record printer, nozzle, material and print orientation in `spec.md`.
3. Plan: write the feature order and user parameters into `progress.md` and get them confirmed (`fusion-parametric-modeling`, or `build123d-modeling` for headless code-CAD).
4. Red: export a placeholder (or run against the empty model) and run `check_part.py`; confirm the checks fail for the right reasons (`geometry-verification`).
5. Model one feature group at a time. After each group: rebuild, export, run `check_part.py`, render one preview if the visible shape changed.
6. Green: all acceptance checks pass. Record the result line in `progress.md`.
7. Review: use `cad-review`. Fix every proven finding, re-run the checks.
8. Export: use `print-export-validation`; `check_mesh.py` must report OK for every printable file.
9. Slice and hand off: slicer project, settings and assembly notes in the design README. State "slice checked", not "tested".
10. Print log: after the user prints, record fit and quality results in `progress.md`. Only now may the design claim "physically tested".
