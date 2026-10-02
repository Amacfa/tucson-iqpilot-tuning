# L2 — launch standstill cap (offline candidate, NOT installed)

## What
`.venv/.../iqdbc/car/hyundai/carcontroller.py`: while `CS.out.standstill`, the
longitudinal accel request is capped at `LAUNCH_HOLD_ACCEL_MAX = 1.0` m/s². The
normal accel clip (`ACCEL_MIN..ACCEL_MAX`) and the L1c jerk-window shaping are
unchanged; once the car rolls, full authority resumes.

## Why (measured, export-v3b)
Brake-release launches command ~2.0 m/s² and the car overshoots badly:

| release cmd | measured launch peaks (aEgo) |
|---|---|
| ~2.0 | 2.86, 3.63, 2.62, 3.83, 3.30, 3.59, 3.84, 3.65, 2.91 |
| 1.28–1.65 | 1.82, 2.52, 2.16, 2.28, 2.41, 2.38 |

Standstill release is the single harshest longitudinal event in the dataset.
Prediction under the 1.0 cap: peaks ~2.0–2.3 m/s².

## Layering
Base = installed L1c candidate (`d3915221`); `layered_over: [L1c]`.
Safety: cap only reduces the accel request at standstill; no limits touched.

## Status
NOT installed — offline candidate only (`readiness: check_only`).
Rollback restores L1c bytes exactly. `manage.py --check/--apply/--rollback` guarded.

## Validation
`validation/test_l2.py` execs the real candidate block: standstill+2.0 → 1.0;
rolling+2.0 → 2.0; negative unchanged; ACCEL_MIN clip preserved. Plus
`test_artifacts.py` (hashes + patch roundtrip + py_compile), `test_manage.py`
(7 guards) — all pass.
