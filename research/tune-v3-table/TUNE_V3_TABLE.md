# tune-v3: LAT_ACCEL_FACTOR_SPEED_TABLE refit

Decision record. Evidence: [LAT_GAIN_FIT.md](LAT_GAIN_FIT.md) (fit_lat_gain.py, v3b export).

## Why not the K_eff fit magnitudes

The raw linear fit (`tqo = ala/K_eff + fric·sign`) reported K_eff of 7–16 m/s² per unit torque at
12–25 m/s — confounded by closed-loop feedback: when actual > desired, the P term pulls torque
back, biasing the implied gain high. K_eff magnitudes are therefore not usable; only the
**tracking ratio** (actual/desired lat accel, same steady-state frames) is used.

## Derivation (first-order correction)

In `torque_from_lateral_accel`, both FF and P are divided by `latAccelFactor`. Raising the table
by a bin's measured tracking ratio lowers FF over-torque and effective P gain together — the
first-order correction for the observed over-turn. Measured v2-group ratios (fit_lat_gain.py):

| bin (m/s) | v2 table@center | measured tracking | scaled value | v3 table interp |
|---|---|---|---|---|
| 5–8 | 2.95 | ~1.0 (0b8c 0.99, v2 nan; baseline 0.855 under-turn) | keep | 2.95 |
| 8–12 | 3.06 | 1.039 | 3.18 | 3.20 |
| 12–15 | 3.26 | 1.193 | 3.88 | 3.80 |
| 15–20 | 3.44 | 1.084 | 3.72 | 3.80 |
| 20–25 | 3.61 | 1.075 | 3.88 | 3.90 |
| 25–40 | 3.70 | 1.33 (baseline only, n=1642) | ~3.9 | 3.90 |

**New table**: `([8.0, 12.0, 15.0, 25.0], [2.95, 3.20, 3.80, 3.90])` — a 4-point table so the
12–15 and 15–20 corrections are resolved separately (they differ: 1.19 vs 1.08).

## Predicted tracking ratio per bin

`predicted ≈ measured × table_v2/table_v3` at bin center (assumes FF-dominated error):

| bin | measured v2 | v2@v3 center | predicted | residual |
|---|---|---|---|---|
| 5–8 | ~1.0 | unchanged | ~1.0 | — |
| 8–12 | 1.039 | 3.06/3.075 | 1.034 | +0.03 |
| 12–15 | 1.193 | 3.26/3.80 | 1.024 | +0.02 |
| 15–20 | 1.084 | 3.44/3.80 | 0.981 | −0.02 |
| 20–25 | 1.075 | 3.61/3.90 | 0.995 | ~0.00 |

Caveat: ratios were measured with P active; P partially compensates FF error, so the true FF
over-torque fraction is larger than (ratio−1) and residual over/under-turn will be nonzero —
predicted values above are optimistic; iterate with real drives. Low-speed (5–8) left unchanged:
baseline under-turn (0.855) predates the speed table entirely; 0b8c/v2 ≈ 1.0.

## Sim deltas (sim_v3_table.py — no refactor, same excitation)

| sim | metric | v2 | v3 |
|---|---|---|---|
| curve-exit (v2_frames, 12 exits) | band_frac torque | 0.518 | 0.518 |
| | band_frac lataccel | 0.380 | 0.380 |
| | dither ×270 | 2.19 | 2.17 |
| curve-exit (drive1, 5 exits) | band_frac torque | 0.634 | 0.633 |
| handback (route 26 seg 6) | ala_pp | 1.021 | 1.033 |
| | band 1–3 Hz | 0.933 | 0.929 |
| | tq_pp | 0.273 | 0.289 |

Sims are wobble-energy neutral (the table changes steady-state gain, not band energy); handback
shows a ~1% degradation (ala_pp 1.033 vs 1.021) — inside sim noise, flagged not hidden.

## Package

`/home/ubuntu/tucson/analysis/tucson-tune-3736edc-v3/package/` — single-file delta on
`iqpilot/selfdrive/controls/lib/latcontrol_torque.py`, layered over tune-v2 (rollback restores
b844c7ed… = current installed file, verified read-only on device 2026-09-29). Validation:
test_table.py, test_artifacts.py (hash/patch roundtrip), test_manage.py — all pass.
**Not installed; offline only.**
