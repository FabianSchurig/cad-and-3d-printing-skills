# Playbook: remodel an existing part

1. Capture: follow `scan-to-sketch` capture rules; get at least one caliper dimension per axis.
2. Outline: run `scan_to_outline.py` with caliper calibration; keep the manifest with scale state and uncertainty.
3. Spec: `cad-spec` with a dimensions table where every value is `measured`, `derived` or `assumed`, and an explicit list of open questions (unseen faces, hidden features).
4. Checks: `checks.json` from caliper values (tolerance = measurement uncertainty), never from the scan alone.
5. Model from fitted lines/arcs and a few fair curves, not from raw scan points. Caliper values override scan values.
6. Compare: overlay the model outline on the scan overlay; report max deviation. Continue with steps 6-10 of the new-part playbook.
