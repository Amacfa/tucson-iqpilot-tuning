# tune v6 — hand-back friction reset (B), ff/fb split wired neutral (release 3736edc)

Single-file delta on `iqpilot/selfdrive/controls/lib/latcontrol_torque.py` vs the
installed v5 file (base sha256 `db166b61…`). Adds a per-car `LAT_TUNE_V6` dict —
unlisted cars take the exact pre-patch path.

## What changes for the driver (knob B, the only active change)

When you take the wheel mid-drive and hand it back, the friction-compensation
memory previously carried stale error into the first moments after hand-back —
felt as a small steering twitch on lane-change exits and hand-backs. Now the
friction error memory resets to zero while you hold the wheel and ramps back in
over 0.25 s after release; it also resets when the requested lateral direction
flips (curve exits). Sims: hand-back lat-accel peak-to-peak 1.007 -> 0.955,
1-3 Hz band 0.923 -> 0.915, tracking rms 0.288 -> 0.269; curve-exit dither
2.15 -> 2.05.

## Wired but neutral (A) / off (C)

- A `split_ff_fb` separates feedforward scaling (speed-scheduled
  latAccelFactor) from P/I scaling (`fb_lat_accel_factor_speed` table). The fb
  table is set identical to the schedule, so on-road behaviour is unchanged —
  it is a lever for future tuning, not a change.
- C (`timing`: lat_delay smoothing + fractional buffer delay) is off:
  `lat_delay_tau: 0.0`, `fractional_delay: false`.

## Linearity finding

`torque_from_lateral_accel` (iqdbc/car/interfaces.py:225) is pure linear
`lat_accel / latAccelFactor`, so the ff/fb split is exact; `pid.update` still
receives `feedforward=ff` so its output clip and anti-windup bound the total
exactly as before.

## Validation (validation/test_v6_equiv.py, real update() on 6000 frames)

- knobs off -> bit-identical to v5
- split A with fb==scheduled -> max diff 7.1e-15
- configured v6 vs v5 -> max delta 0.0244 torque units (B ramp only), 0 frames > 1.0

Offline only — not installed, not driven.
