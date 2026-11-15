# Playbook: print failure or bad fit

1. Use `print-failure-diagnosis`: build the fastest repeatable test first (coupon, caliper reading, or a check that reproduces the misfit).
2. List 3-5 falsifiable hypotheses, ranked; change one variable per test.
3. Fix the cause where it lives: spec value, model parameter, slicer setting or material.
4. Add a regression check (`checks.json` value or `spec.md` rule) and log the result in `progress.md`.
