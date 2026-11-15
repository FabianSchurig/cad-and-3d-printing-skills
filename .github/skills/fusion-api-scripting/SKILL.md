---
name: fusion-api-scripting
description: Write and run Autodesk Fusion API (adsk.core / adsk.fusion) Python scripts through the Fusion MCP server or the Scripts dialog. Use when automating Fusion modelling, building a design from a script, inspecting a Fusion design programmatically, or when a Fusion script fails, times out, or produces wrong dimensions.
---

# Fusion API scripting

## Connecting

- Enable the MCP server in Fusion's preferences. It serves `http://127.0.0.1:27182/mcp` (default port). Register that URL as an HTTP MCP server in your client (`.vscode/mcp.json` or `~/.copilot/mcp-config.json`).
- **Fusion on Windows, workspace in WSL:** `127.0.0.1` from WSL only reaches Windows with `networkingMode=mirrored` in `%UserProfile%\.wslconfig`.
- Look up API classes and members with `fusion_mcp_read` → `queryType: "apiDocumentation"` before guessing signatures.

## Script contract (`fusion_mcp_execute`, `featureType: "script"`)

- The script must define `def run(_context: str):`.
- `print()` output is returned as the tool result.
- **Never catch exceptions** in `run`. The traceback is the only way to see where and why the script failed.
- Pass `readOnly: true` for scripts that only inspect the design. Only read-only scripts can run while the user has a command dialog open.
- A script that raises is rolled back: Fusion undoes all its changes. Re-run the fixed script; do not clean up by hand.
- Do not save the document (cloud version) unless the user explicitly asks. Persist work by exporting `.f3d`/`.step`/`.stl` into the project folder instead. Once the user asked, save after each verified change with a message saying what changed.

## Units

The API works internally in **centimetres**. Keep design intent in mm and convert at the boundary:

```python
def vi(expr):  # "12 mm", "D_outer - 2 * t_wall", "15 deg"
    return adsk.core.ValueInput.createByString(expr)


def p3(x_mm, y_mm, z_mm):
    return adsk.core.Point3D.create(x_mm / 10, y_mm / 10, z_mm / 10)


def pv_mm(name):  # parameter value in mm
    return design.allParameters.itemByName(name).value * 10
```

Bounding boxes, `pointContainment` probes, volumes (cm³) and areas (cm²) are all in cm units too.

## File paths between WSL and Fusion

Fusion's Python runs on Windows. Any path it opens or writes must be a Windows path. Convert with `wslpath -w /home/<user>/<project>`, which gives `\\wsl.localhost\<Distro>\home\<user>\<project>`. Fonts used by text features live in `C:\Windows\Fonts` (from WSL: `/mnt/c/Windows/Fonts`).

## Large builds: script file + staged loader

Keep the real build script in the project folder. Load it once, then drive it in stages, one MCP call per slow stage. A single call has a timeout, and features like text emboss or many-profile extrudes on curved faces take minutes each.

```python
BUILD = r"\\wsl.localhost\<Distro>\home\<user>\<project>\fusion\build.py"


def run(_context: str):
    g = {"__file__": BUILD, "__name__": "build"}  # exec() sets neither
    exec(open(BUILD, encoding="utf-8").read(), g)
    g["run_stages"](["params", "profile", "split"])
```

In the build script:

- One function per stage, plus a `run_stages(names)` that prints `stage ok: <name> timeline <count>` after each one.
- Make stages re-runnable. `stage_params` updates existing user parameters instead of adding duplicates. Find bodies by name rather than by index.
- Provide a fast reset: `tl.markerPosition = 0; tl.deleteAllAfterMarker()`. This is much faster than deleting features one by one.
- **Collapse timeline groups before deleting or rebuilding** (`group.isCollapsed = True`). If the user expanded a group, `deleteMe()` on its features fails with `InternalValidationError: res`.
- Delete obsolete objects explicitly (`occurrence.deleteMe()`, `sketch.deleteMe()`, `design.userParameters.itemByName(n).deleteMe()`), latest first, after deleting joints that reference them; then check volumes and timeline health.
- Append progress to a log next to the script (`HH:MM:SS stage X ok 72s`). Long sessions can then be resumed and timed.
- Set `sketch.isComputeDeferred = True` while adding many sketch entities.
- If a feature needs minutes per instance (for example embossing hundreds of traced profiles), move that geometry to a local mesh pipeline instead (`manifold3d`/`trimesh`). Union it at print-prep time; it does not need to be a Fusion feature.

## Snippets

[references/snippets.md](references/snippets.md) has ready-to-paste code for:

- a read-only **design inventory**: bodies, volumes, face counts, sketch constraint state, timeline health, parameters. Run it at the start of a turn.
- reading the **user's current selection**: when the user marks a spot in a screenshot, ask them to select it in Fusion instead.
- **fully constraining** polyline sketches from code.
- **STL / .f3d export and save**, including STL settings that pass the 0.01 % volume gate, and component vs. assembly frames.

## Guard rails

```python
def require(value, message):
    if not value:
        raise RuntimeError(message)
    return value
```

- Wrap every `...add(...)` result in `require(...)` so a `None` fails loudly, with context.
- Fusion adds implicit horizontal/vertical constraints. Adding the same dimension again raises an error containing `OVER_CONSTRAINTS`. Catch only that case, skip the dimension, and re-raise everything else.
- Every sketch the script creates ends **fully constrained** (`sketch.isFullyConstrained`); raise otherwise. The user sees blue sketches as unfinished work.
- Before modifying, check you are in the expected document (`app.activeDocument.name`). A setup script meant for an empty design should refuse to run on a non-empty one rather than duplicate work.
- Feature direction can flip silently (revolve/extrude side). Probe with `body.pointContainment(point)` and flip the extent if the wrong side was cut.

## Check each change

| After | Check in Fusion | Then outside Fusion |
|---|---|---|
| Any stage | Timeline health: print `item.name`, `item.errorOrWarningMessage` for every item whose `healthState` is not healthy | — |
| Solid features | Body count, names, bounding boxes, volumes; interference between mating parts | Export STL, run `check_part.py` (`geometry-verification`) |
| Holes, slots, pockets, insertion paths | `body.pointContainment(point)` probes | `empty_at` probes in `checks.json` |
| Visible shape change | `fusion_mcp_read` → `queryType: "screenshot"`, one view | — |
| Before hand-off | All of the above | `check_mesh.py` (`print-export-validation`) |

Write results to a log or `progress.md` so later sessions can trust them. Read numbers from checks, never from screenshots.
