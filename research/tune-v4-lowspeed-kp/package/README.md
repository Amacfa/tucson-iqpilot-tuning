# tune v4 — low-speed P reduction (layered over H1, release 3736edc)

Single-file delta on `iqpilot/selfdrive/controls/lib/latcontrol_torque.py` vs the H1
candidate (pre-state sha256 `97cc8ee4…` = currently installed H1 file):

`kp_scale = np.interp(vEgo, [13,17], [1.0,0.6])` → `[0.7,0.6]` — P gain is now **×0.7
below 13 m/s**, blending to ×0.6 at 17 m/s (was ×1.0 below 13). Comment updated.
Everything else byte-identical to H1 (keeps the kp interp, the 0.3 s friction-error LP,
and the v3 speed table).

## Rationale (from `analysis/wobble/V3H1D1_MECHANISM.md`)

First-drive data (route 0000002d) showed all remaining P-dominated problems at ≤13 m/s,
i.e. **below H1's 13 m/s ramp-in**:

- the felt wobble episode: 1.67 Hz, p_rms 1.29 > f_rms 1.08, at **10.8 m/s**;
- two P-led saturation events during override settle (p ≈ 2.5) at **6.6–7.4 m/s**;
- mechanism replay cleared D1 lookahead and the H1 friction LP as torque causes.

v4 cuts low-speed P by 30%. If insufficient, next step is 0.6 flat (single number change).

## Sims (no regression)

- sim_handback (route-26-seg-6 excitation, v3 table, kp_lowspeed_scale=0.7): see RESULTS
  (ala_pp ≈ 0.5x retained, no low-speed degradation — excitation is ≥17 m/s so unchanged).
- sim_curve_exit: unchanged (kp_lowspeed_scale already parameterized; 0.7 ≈ v3 base).

Install order: tune-v3 → H1 → **v4** (replaces H1 file) → D1. Rollback restores the H1
candidate file. `manage.py --check | --apply | --rollback | --verify-installed` (parked).
Not installed.
