# Playbook: size variants

1. Confirm the master design is green on its checks and fully parametric (change a key parameter once and verify the geometry follows).
2. Define the variant table in `spec.md`: parameter values, nominal mating size, and which values stay fixed (walls, hooks, clearances).
3. Generate each variant by setting parameters and re-exporting; never scale meshes.
4. For each variant: derive its `checks.json` values from the variant table, run `check_part.py` and `check_mesh.py`.
5. Name files after the nominal size (`Part_Tube14p5mm_Rod2-3mm.stl`) and write a manifest with parameters, check results and checksums.
