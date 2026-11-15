# build123d cheat sheet (algebra mode)

| Need | Code |
|---|---|
| Primitive at a position | `Pos(x, y, z) * Box(w, d, h)`, `Cylinder(r, h)`, `Sphere(r)`, `Cone(r1, r2, h)` |
| Rotate | `Rot(0, 0, 45) * shape` |
| Boolean | `a + b` (union), `a - b` (cut), `a & b` (intersect) |
| 2D sketch → extrude | `extrude(Rectangle(w, d) - Circle(r), amount=h)` |
| Revolve a profile | `revolve(Plane.XZ * Polygon(...), Axis.Z)` |
| Fillet / chamfer edges | `fillet(part.edges().filter_by(Axis.Z), r)`, `chamfer(part.edges().group_by(Axis.Z)[0], 0.3)` |
| Select faces/edges | `.faces().sort_by(Axis.Z)[-1]` (top), `.edges().filter_by(GeomType.CIRCLE)`, `.group_by(Axis.Z)` |
| Pattern | `PolarLocations(r, n) * Cylinder(...)`, `GridLocations(dx, dy, nx, ny) * Box(...)` |
| Text | `extrude(Text("ABC", font_size=8), amount=0.8)` |
| Shell | `offset(part, amount=-t, openings=part.faces().sort_by(Axis.Z)[-1])` |
| Import | `import_step("x.step")`, `import_stl("x.stl")` (mesh, not editable BRep) |
| Export | `export_step`, `export_stl(part, path, tolerance, angular_tolerance)`, `Mesher` for 3MF |
| Properties | `part.volume`, `part.bounding_box().size`, `part.is_valid`, `len(part.solids())` |

Pitfalls

- Units are mm. Primitives are centred on the origin by default; set `align=(Align.CENTER, Align.CENTER, Align.MIN)` to sit on z = 0.
- A failing fillet usually means the radius exceeds an adjacent face; fillet before cutting small features, or reduce the radius.
- `len(part.solids()) > 1` after a union means the parts did not overlap; add a small overlap (≥ 0.01 mm).
- Selectors on sorted faces break when topology changes; prefer selecting by geometry (`filter_by`, `group_by`) over indices.
- STL import yields a mesh; boolean it with `manifold3d`/`trimesh`, not with build123d.
