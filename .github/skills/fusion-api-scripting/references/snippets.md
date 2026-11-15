# Fusion snippets: inventory, selection, constraints, export

Paste these into `fusion_mcp_execute` (`featureType: "script"`) or into the design's build script. They use only `adsk.*` and run inside Fusion; they are not uv scripts.

## Design inventory (read-only, run at the start of each turn)

One call gives the state that otherwise takes many ad-hoc probes: bodies with volumes, sketches with their constraint state, timeline health and groups, user parameters. Pass `readOnly: true`.

```python
import adsk.core, adsk.fusion


def run(_context: str):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    print("document:", app.activeDocument.name, "modified:", app.activeDocument.isModified)
    for comp in design.allComponents:
        for b in comp.bRepBodies:
            print(
                f"body  {comp.name}/{b.name}: {b.volume:.4f} cm3, faces {b.faces.count}, visible {b.isVisible}"
            )
        for sk in comp.sketches:
            state = "ok" if sk.isFullyConstrained else "UNDER-CONSTRAINED"
            print(f"sketch {comp.name}/{sk.name}: {state}, profiles {sk.profiles.count}")
    tl = design.timeline
    healthy = adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState
    for i in range(tl.count):
        it = tl.item(i)
        if it.isGroup:
            print(f"group {it.name}: collapsed {it.isCollapsed}")
        elif it.healthState != healthy:
            print(f"UNHEALTHY {i} {it.name}: {it.errorOrWarningMessage}")
    print("timeline items:", tl.count)
    for p in design.userParameters:
        print(f"param {p.name} = {p.expression}  # {p.comment}")
```

Use it to answer "what is left from the old version?": bodies, sketches and parameters that the spec's part list does not name are candidates for deletion.

## What did the user mark?

Screenshots with drawn markings are hard to map to geometry. Ask the user to **select** the face, edge or body in Fusion (keep the selection, no command open), then read it:

```python
def run(_context: str):
    ui = adsk.core.Application.get().userInterface
    for i in range(ui.activeSelections.count):
        e = ui.activeSelections.item(i).entity
        bb = e.boundingBox
        owner = getattr(e, "body", None)
        print(
            e.objectType,
            getattr(e, "name", ""),
            "body:",
            owner.name if owner else "-",
            "bbox mm:",
            [
                round(v * 10, 2)
                for v in (
                    bb.minPoint.x,
                    bb.minPoint.y,
                    bb.minPoint.z,
                    bb.maxPoint.x,
                    bb.maxPoint.y,
                    bb.maxPoint.z,
                )
            ],
        )
```

Then turn the location into a probe or an assembly check before changing the model.

## Fully constrained polygon sketches

Fusion does not constrain sketches created from code. For sketches made of straight polylines, fix every point in sketch x and y: align it (vertical/horizontal points constraint) with the origin or an earlier point at the same coordinate, otherwise add a distance dimension from the origin. Fail the build if the sketch is still blue.

```python
def constrain_points(sk):
    org = sk.originPoint
    gc, dims = sk.geometricConstraints, sk.sketchDimensions
    H = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
    V = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation
    seen_x, seen_y = {0.0: org}, {0.0: org}
    for pt in list(sk.sketchPoints):
        if pt == org or pt.isReference or not pt.connectedEntities or pt.connectedEntities.count == 0:
            continue
        g = pt.geometry
        kx, ky = round(g.x, 6) + 0.0, round(g.y, 6) + 0.0
        for key, seen, align, orient, text in (
            (kx, seen_x, gc.addVerticalPoints, H, adsk.core.Point3D.create(g.x / 2, g.y + 0.3, 0)),
            (ky, seen_y, gc.addHorizontalPoints, V, adsk.core.Point3D.create(g.x + 0.3, g.y / 2, 0)),
        ):
            try:
                if key in seen:
                    align(seen[key], pt)
                else:
                    dims.addDistanceDimension(org, pt, orient, text)
                    seen[key] = pt
            except RuntimeError as err:  # already fixed by an implicit constraint
                if "OVER_CONSTRAINTS" not in str(err):
                    raise
    if not sk.isFullyConstrained:
        free = [
            (round(q.geometry.x * 10, 2), round(q.geometry.y * 10, 2))
            for q in sk.sketchPoints
            if not q.isFullyConstrained
        ]
        raise RuntimeError(f"sketch {sk.name} not fully constrained, free points (mm): {free[:6]}")
```

Draw connected polylines (each line starts at the previous end point), not separate segments, or every corner becomes two points. Set `sk.isComputeDeferred = True` while adding many constraints. For arcs and splines, add the constraints by hand; dimensions that drive design intent should reference user parameters (`dim.parameter.expression = "wall_t"`).

## Export and save

```python
em = design.exportManager
# STL fine enough for the 0.01 % volume gate on curved parts; High is often too coarse
opts = em.createSTLExportOptions(body, stl_path)  # stl_path from `wslpath -w`
opts.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementCustom
opts.surfaceDeviation = 0.001  # cm
opts.normalDeviation = 0.1  # rad
opts.isBinaryFormat = True
em.execute(opts)

# local archive next to the model script
em.execute(em.createFusionArchiveExportOptions(f3d_path))

# cloud version: only when the user asked to save
app.activeDocument.save("what changed and why")
```

A native component body exports in its component's coordinates. For several parts in one shared frame, export the occurrence proxy (`body.createForAssemblyContext(occurrence)`) or record the offset in the spec's Frames section. Compare the exported bounds with the expected ones before running assembly checks.
