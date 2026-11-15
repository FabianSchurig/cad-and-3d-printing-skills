---
name: cad-workflow
description: Run a CAD-for-3D-printing task end to end through phase gates (spec, verify-first, model, review, export, print log). Start here for a new part, a change, a remodel from a scan, size variants, a print failure, or pausing/resuming work.
argument-hint: "What do you want to design, change or fix?"
disable-model-invocation: true
---

# CAD workflow

1. **Restate** the goal in one sentence and name the smallest deliverable (e.g. "one STL that fits a 14.5 mm tube"). Do not wait for confirmation unless something is ambiguous.
2. **Pick one playbook** and copy its steps verbatim into your todo list. Mark a step you skip as `skip: <reason>`; never drop one silently.

| Task | Playbook |
|---|---|
| New part from an idea or requirements | [new-part](playbooks/new-part.md) |
| Change an existing design | [change-part](playbooks/change-part.md) |
| Remodel an existing physical part (scan, photo, calipers) | [remodel-from-scan](playbooks/remodel-from-scan.md) |
| Several sizes of one design | [size-variants](playbooks/size-variants.md) |
| A print failed, warped or does not fit | [print-failure](playbooks/print-failure.md) |
| Stop now and continue later / pick up earlier work | [pause-and-resume](playbooks/pause-and-resume.md) |

3. **Gates.** Finish each phase in a checkable state before starting the next: spec agreed → checks red → model → checks green → review → export validated → printed and logged.

## Design folder layout

Every design lives in its own folder and is self-contained:

```text
<design>/
  spec.md        requirements, dimensions (value, source, tolerance), process, out of scope
  checks.json    acceptance checks for check_part.py, written before modelling
  assembly.json  fit, slide and seal checks for check_assembly.py (designs with mating parts)
  progress.md    phase checklist, frames, commands, decision log, print log, gotchas, handoff notes
  model/         Fusion build script or build123d model.py (parameters at the top)
  out/           exports, previews, reports (regenerated, never edited by hand)
```

Start `progress.md` from the [progress template](references/progress-template.md); its Commands, Frames and Gotchas sections save the next session from rediscovering them.

## Principles

- **Prove it on the real artefact.** A model is done when checks on the exported geometry pass, not when the script runs.
- **One verified unit at a time.** Small step, run the checks, then the next step.
- **Settle empirical questions with a test coupon**, not with debate. Ask the user only about preferences and facts you cannot measure.
- **Never shrink to pass.** If a check fails, fix the design; do not drop or weaken a specified feature or check.
- **Encode repeated lessons** as a check in `checks.json` or a rule in `spec.md`, not as prose you hope to remember. When the user finds a defect your checks missed, first add the check that would have caught it and watch it fail, then fix the model.
- **Keep the context small.** Use scripts for deterministic work; read their summary lines, not the meshes.
