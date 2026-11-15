# <Part name> – progress

## Status
Goal in one sentence. Current phase (spec / checks red / model / checks green / review / export / printed). Last check run and its result line.

## Checklist
- [ ] Spec agreed
- [ ] Checks red on the old/placeholder model
- [ ] Model changed, old version retired (no orphan bodies or sketches, all sketches fully constrained)
- [ ] Part and assembly checks green
- [ ] Review done
- [ ] Export validated (mesh gate), slicer project updated, slice checked
- [ ] Printed and fit-tested (physical; keep apart from "slice checked")

## Frames
Which coordinate frame each export uses and the offsets between them (e.g. "lid and bin in the bin frame; connectors in world frame = bin frame + 47.5 z"). Every multi-part check and section image uses one frame.

## Commands
Copy-paste lines that reproduce the current state, run from the design folder:

```bash
# build (CAD back end and how stages are invoked)
# part checks:      uv run <skills>/geometry-verification/scripts/check_part.py checks.json
# assembly checks:  uv run <skills>/geometry-verification/scripts/check_assembly.py assembly.json
# print prep:       uv run <skills>/print-export-validation/scripts/place_on_bed.py ...
# mesh gate:        uv run <skills>/print-export-validation/scripts/check_mesh.py ...
# slicer project:   uv run <skills>/print-export-validation/scripts/update_3mf_project.py ...
# slice:            see print-export-validation/references/slicer-cli.md
```

## Decision log
| Change | Decision | Why / evidence |
|---|---|---|

## Print log
| Date | Part | Printer / material / settings | Result | Slice checked or physically tested |
|---|---|---|---|---|

## Gotchas
Tool quirks found in this design, so they are not rediscovered (API errors and their fixes, slow stages and their run times).

## Open items / next steps
1. ...
