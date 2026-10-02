# tune-v6 — ff/fb split + handback friction + delay timing (offline, NOT installed)

Base file: installed v5 `latcontrol_torque.py` (`db166b61`). One file changed:
`iqpilot/selfdrive/controls/lib/latcontrol_torque.py`. Per-car dict
`LAT_TUNE_V6 = {"HYUNDAI_TUCSON_4TH_GEN": {...}}` — unlisted cars take the exact
pre-patch path (verified bit-identical below).

## Linearity finding (required for knob A)

`CI.torque_from_lateral_accel` for Hyundai is `torque_from_lateral_accel_linear`
(iqdbc/car/interfaces.py:225-227): `lateral_acceleration / latAccelFactor` — pure
linear scale, no offset or friction inside (friction is added by the caller into
`ff`). So `output = (p+i+ff)/F` splits cleanly into `ff/F_sched + (p+i)/F_fb`.

Two subtleties found while implementing:

1. **PID output clip**: real `iqpilot/common/pid.py` `update()` clips
   `control = p+i+d+f` to `[neg_limit, pos_limit]` (and anti-windup checks
   `test_control` including `f`). Naively calling `pid.update(feedforward=0)`
   would clip only `p+i` and add `ff` unclipped — total torque could exceed
   steer_max and equivalence breaks at saturation. Fix: keep `feedforward=ff`
   in the pid call (so clip + anti-windup + `pid_log.f` are unchanged), then
   `fb_lataccel = output_lataccel - ff` and split in torque space. When
   `F_fb == F_sched` this is bit-identical to v5 (verified: max diff 7e-15).
2. `pid_log.f` needs no special handling with this approach (`self.pid.f`
   still holds `ff`).

## Knobs (LAT_TUNE_V6, Tucson entry)

- **A** `split_ff_fb: true`, `fb_lat_accel_factor_speed`: P/I torque scales by
  this per-car table instead of the speed schedule. Configured **identical to
  LAT_ACCEL_FACTOR_SPEED_TABLE** ([8,12,15,25] -> [2.95,3.45,4.05,4.05]) — the
  lever is wired but neutral (first config used scalar 2.960174, which would
  have made P/I ~37% stronger at 25 m/s; rejected).
- **B** `handback: {blend_s: 0.25, fric_reset_on_reversal: true}`: while
  `steeringPressed`, `_fric_err_lp` resets to 0 and the friction term is
  ramped 0→1 over 0.25 s after release; sign flips of `setpoint` above the
  lateral-accel deadzone reset `_fric_err_lp`; while inactive `_fric_err_lp`
  is held at 0.
- **C** `timing: {lat_delay_tau: 0.0, fractional_delay: false}` — OFF for the
  first install (smoothed `lat_delay` + fractional buffer interpolation are
  implemented but disabled; neutral in sims at constant delay).

## Checks

`py_compile` clean. `test_v6_equiv.py` (execs v5 + v6 with stubbed deps, drives
the real `update()` over 6000 drive frames):

```json
{"knobs_off_bit_identical": true,
 "splitA_fb_eq_sched_max_abs_diff": 7.105427357601002e-15,
 "splitA_within_1e-9": true,
 "full_v6_finite": true,
 "full_v6_max_abs_delta_vs_v5": 5.132036819014999}
```

## Harness results (reused sim_curve_exit.py / sim_handback.py with v6 knobs added)

Curve-exit sim (v2_frames.npz, 12 exits, v5 table):

| variant | band_frac_torque | band_frac_lataccel | dither_x270 |
|---|---|---|---|
| v5 | 0.519 | 0.381 | 2.15 |
| v5+A | 0.523 | 0.384 | 2.19 |
| v5+B | 0.516 | 0.379 | 2.05 |
| v5+C | 0.519 | 0.381 | 2.15 |
| v5+A+B+C | 0.526 | 0.384 | 2.09 |

(logged reference: band_tq 0.504, band_ala 0.433)

Handback sim (route 26 seg 6, lane-change hand-back; real: ala_pp 1.71):

| variant | ala_pp | ala_rms | band_1_3 | tq_pp | track_rms |
|---|---|---|---|---|---|
| v5 | 1.007 | 0.292 | 0.923 | 0.284 | 0.288 |
| v5+A | 0.995 | 0.290 | 0.948 | 0.264 | 0.295 |
| v5+B | 0.955 | 0.280 | 0.915 | 0.260 | 0.269 |
| v5+C | 1.007 | 0.292 | 0.923 | 0.284 | 0.288 |
| v5+A+B+C | 1.018 | 0.295 | 0.949 | 0.271 | 0.297 |

## Delta analysis (configured v6 vs v5, 6000 replay frames)

Earlier scalar-fb config produced max delta 5.13 — that was P/I torque scaled
by 2.96 vs schedule up to 4.05 (~37% stronger at speed), the exact over-hot
correction rejected. With the fb table == schedule, A is bit-neutral and the
only deltas come from knob B: max 0.0244 torque units, 0 frames > 1.0. Top
frames (i 473-484, v~7.4 m/s, act=True, prs=False): the 0.25 s friction ramp
re-engaging after a steeringPressed reversal-reset — expected, bounded.

## Read

- **B** (active) improves hand-back metrics (ala_pp 1.007->0.955, band_1_3
  0.923->0.915, track_rms 0.288->0.269; curve-exit dither 2.15->2.05).
- **A** is wired but configured identical to the schedule — bit-neutral.
- **C** is off.

Packaged at analysis/tune-v6-handback/package — not installed, not driven.
