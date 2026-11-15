# Playbook: pause and resume

**Pause.** Update `progress.md` (layout: [progress template](../references/progress-template.md)) so a fresh session can continue without this conversation:

- Goal and current phase; the last check run and its result line.
- Parameter values changed since the spec; open questions; next 1-3 steps.
- Pointers, not copies: paths to the spec, checks, model script and newest outputs.
- Which skills the next session should load.
- The exact commands that reproduce the state, the coordinate frames of the exports, and the tool gotchas found so far.

**Resume.** Read `progress.md`, `spec.md` and `checks.json`, run the checks to confirm the recorded state, then continue at the recorded next step. Trust the recorded trail; do not redo finished phases.
