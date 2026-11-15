# Playbook: change an existing part

1. Read the design folder's `spec.md`, `progress.md` and README first. If none exist, create `spec.md` from what the folder and model show (`cad-spec`) and mark unverified values as assumed.
2. Update `spec.md` and `checks.json` for the change *before* touching the model. Add a check that fails on the current model and passes only with the change.
3. Run the checks: the new check is red, all existing checks stay green. A new check that is already green on the old design is suspect; tighten it until it fails for the reason you expect.
4. Change the model through parameters or the owning feature group; do not patch geometry downstream of it.
5. Retire the old version: list every body, sketch, feature, joint and parameter the change makes obsolete, delete them, and confirm that the remaining volumes and timeline health are unchanged. Look again at the faces the old feature touched: no seam or leftover cut.
6. Re-run all checks, then `cad-review` on the changed area, then `print-export-validation` for affected parts.
7. Record the decision (what changed, why, evidence) in `progress.md` and bump the variant/file names if outputs changed.
