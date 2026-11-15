# Slicing a project from the command line

A CLI slice proves that the project slices in bounds with its own presets, and gives the layer count, time and filament estimates for the print log. It is **slice checked**, not printed. Never send the result to a printer unless the user asks.

## Bambu Studio / OrcaSlicer

Both accept a project 3MF and slice all plates with the presets stored in it:

```bash
bambu-studio --slice 0 --outputdir out/slice project.3mf        # 0 = all plates, N = plate N
orca-slicer  --slice 0 --outputdir out/slice project.3mf
```

Read the results:

- `out/slice/result.json`: return code and error string (`"return_code": 0` means sliced). Some versions also write per-plate warnings.
- The G-code header, `out/slice/plate_<n>.gcode` (or inside the written 3MF): the `; total layer number:`, `; estimated printing time` and `; total filament weight` lines. Their exact wording varies by version, so grep for `layer`, `time` and `filament`.
- Note the slicer version (`--help` prints it), and whether supports or brims were generated, in the print log.

## Slicer on Windows, workspace in WSL

The Windows executable cannot read `\\wsl.localhost\...` paths reliably. Copy the project to a Windows temp folder, slice there, and read the results back:

```bash
win_tmp=/mnt/c/Users/<user>/AppData/Local/Temp/slice_job
mkdir -p "$win_tmp/out" && cp project.3mf "$win_tmp/in.3mf"
"/mnt/c/Program Files/Bambu Studio/bambu-studio.exe" --slice 0 \
  --outputdir "$(wslpath -w "$win_tmp/out")" "$(wslpath -w "$win_tmp/in.3mf")"
cat "$win_tmp/out/result.json"; grep -m3 -i "total layer" "$win_tmp"/out/*.gcode
rm -rf "$win_tmp"   # clean up afterwards
```

## Updating a project after a model change

Keep the user's presets: swap meshes with `scripts/update_3mf_project.py` instead of building a new project from scratch. It drops stale embedded G-code. Then slice again and compare the layer count and filament weight with the previous print log entry: a large jump without a matching design change means the wrong mesh or orientation.
