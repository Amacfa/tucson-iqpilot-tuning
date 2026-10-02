# S2 — stopped-lead distance (offline candidate, NOT installed)

## What
`iqpilot/selfdrive/controls/lib/longitudinal_mpc_lib/long_mpc.py`:
`STOP_DISTANCE = 3.0` → `4.0` — one line. Used by `get_safe_obstacle_distance`
(`v²/2·COMFORT_BRAKE + t_follow·v + STOP_DISTANCE`).

## Why (measured)
In Experimental-mode routes 3e–42, measured stopped-lead gaps were 1.8–3.0 m with
STOP_DISTANCE 3.0 — tighter than the constant implies (delivery/measurement loss).
Expected under 4.0: +1.0 m.

## Side effect (documented)
The constant also feeds the MPC following distance at all speeds, so following
margin grows +1.0 m at speed — small relative to `t_follow·v` (≈ +5% at 20 m/s
with relaxed 1.75 s).

## Layering / safety
Independent of every other package (`independent_of_tune_package: true`); single
constant; increases margins only — no limits touched.

## Status
NOT installed — offline candidate only (`readiness: check_only`).
Rollback restores `2b6c5057` (stock constant).

## Validation
`validation/test_s2.py` lifts the constants + function from the candidate source:
`f(0, t)=4.0`; `f(10 m/s, 1.45)=20+14.5+4=38.5`; asserts exactly one line differs.
Plus `test_artifacts.py` and `test_manage.py` — all pass.
