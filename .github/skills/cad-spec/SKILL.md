---
name: cad-spec
description: Write or update a part spec (spec.md) and its machine-readable acceptance checks (checks.json) before modelling - requirements, mating dimensions with source and tolerance, process, out of scope. Use when starting a part, when requirements, fits, loads or orientation are unclear, or when a change request arrives.
---

# Part spec

## 1. Close the gaps first

Read what exists (design folder, photos, scans, measurements, the CAD model) yourself. Then ask the user only what you cannot find out, in numbered rounds, each question with your recommended answer. Ask the whole open frontier in one round. Typical gaps: function and load, the model's coordinate frame, mating parts and their measured sizes, fit type, printer/nozzle/material, orientation and visible faces, quantity, out of scope.

## 2. Write `spec.md`

Use the [template](references/spec-template.md). Rules:

- Every dimension row has a **value, unit, source and tolerance**. Sources: `measured` (instrument, who/when), `datasheet` (link), `derived` (formula from other rows), `assumed` (why). Never present an assumed value as measured.
- Fits are stated as a clearance per side, with the mating part's measured size.
- List open questions and out-of-scope items explicitly; an empty list is a claim.

## 3. Write `checks.json`

Translate each verifiable requirement into an acceptance check for `check_part.py` (format in the `geometry-verification` skill). Expected values come from the spec rows, never from reading the model. Each check gets a `why` naming the spec row. Put the spec values that several probes depend on (top height, wall position) into `"datums"` named after their rows and write probe coordinates relative to them, so a change request edits one value. Fits, sliding parts and seals between parts go into `assembly.json` for `check_assembly.py`. Requirements that geometry cannot verify (strength, feel, colour) go into `spec.md` under "verified by print test".

## 4. Confirm

Show the user the dimensions table and the out-of-scope list and get confirmation before modelling. Record later changes in the spec's change log with the reason.
