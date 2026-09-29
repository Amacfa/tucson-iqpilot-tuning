# Steering delay fit (v3b export)

Script: `/home/ubuntu/tucson/analysis/wobble/delay_fit.py`
Method: engaged+lat-active+unpressed+|tqo|<0.9 stretches ≥ 8 s; high-pass (subtract 1 s rolling
mean); lag of max cross-correlation, `x[:-L]` vs `y[L:]`, L ∈ [0, 0.8 s] at ~100 Hz export rate.
(a) −tqo vs `rate` (steering angle rate) — actuator delay proper;
(b) −tqo vs d/dt(`ala`) — plant response delay.

## Measured lags (median [IQR], corr)

### 0b8c190c_pre_tune
| bin | n | lag_rate | corr | lag_d(ala)/dt | corr |
|---|---|---|---|---|---|
| 5–10 | 4 | 0.060 [0.037–0.200] | 0.11 | 0.050 [0.045–0.055] | 0.27 |
| 10–15 | 13 | 0.150 [0.080–0.280] | 0.09 | 0.040 [0.040–0.040] | 0.27 |
| 15–20 | 8 | 0.280 [0.038–0.628] | 0.14 | 0.030 [0.030–0.042] | 0.33 |

### baseline_pre0b8c190c
| bin | n | lag_rate | corr | lag_d(ala)/dt | corr |
|---|---|---|---|---|---|
| 5–10 | 18 | 0.250 [0.072–0.473] | 0.10 | 0.050 [0.040–0.060] | 0.29 |
| 10–15 | 63 | 0.330 [0.105–0.590] | 0.10 | 0.040 [0.030–0.040] | 0.25 |
| 15–20 | 42 | 0.300 [0.062–0.475] | 0.11 | 0.040 [0.030–0.040] | 0.41 |
| 20–25 | 4 | 0.160 [0.105–0.315] | 0.12 | 0.035 [0.030–0.042] | 0.35 |
| 25–40 | 4 | 0.225 [0.150–0.262] | 0.05 | 0.025 [0.015–0.030] | 0.21 |

### v2 (routes 25–2c)
| bin | n | lag_rate | corr | lag_d(ala)/dt | corr |
|---|---|---|---|---|---|
| 5–10 | 2 | 0.338 [0.202–0.474] | 0.13 | 0.063 [0.062–0.064] | 0.39 |
| 10–15 | 20 | 0.242 [0.046–0.438] | 0.11 | 0.044 [0.033–0.044] | 0.24 |
| 15–20 | 24 | 0.245 [0.065–0.556] | 0.09 | 0.033 [0.024–0.037] | 0.33 |
| 20–25 | 4 | 0.231 [0.176–0.272] | 0.29 | 0.033 [0.033–0.036] | 0.49 |

(v1_route24: 3 stretches total — 0.787/0.506 s rate-lag outliers at corr ~0.1; not meaningful.)

## Reading

- The **d(ala)/dt lag is tight and consistent: ~0.03–0.06 s** across all groups and speeds,
  corr 0.2–0.5. The torque→latAccel rate-of-change response is fast; there is no evidence for a
  ~0.3 s actuator transport delay in the data.
- The **steering-angle-rate lag is diffuse** (corr ≈ 0.1, IQR spanning the whole search range):
  `rate` (steering angle velocity) is dominated by slow driver/hand dynamics, not a clean
  actuator impulse response — usable only as a weak corroboration.
- Field note: `carState.yawRate` is all-zero in the export (IQ doesn't populate it), so d(ala)/dt
  (torqueState.actualLateralAccel derivative) is the only usable response signal.

## What the device assumes

- `iqdbc/car/hyundai/interface.py`: `ret.steerActuatorDelay = 0.1` common CAN-FD Hyundais
  (0.2 only for KIA_OPTIMA_G4_FL — Tucson uses **0.1 s**).
- Used in two places:
  - `latcontrol_torque.py:241` `desired_lat_jerk_time = steerActuatorDelay + LAG_EXTRA_S` (jerk lead).
  - `controlsd.py:271`: `lat_delay = lateral_action_delay(params, CP, sm['lateralDelay'].lateralDelay)
    + LAT_SMOOTH_SECONDS` → request-buffer lookahead `delay_frames` in `LatControlTorque.update`.
    `steer_delay.py`: torque cars return **live_delay** (the lagd-learned value), NOT
    steerActuatorDelay; only ANGLE cars fall back to the fixed value.
- Device param `LiveDelay` (read-only decode, `lateralDelay` field):
  `lateralDelay = 0.30 s, valid=True, status='unestimated', calPerc=0, validBlocks=0, version=1`
  → lagd has **not learned anything**; the 0.30 s is the unestimated design default.
  So the effective lookahead delay used by tune-v2 is **0.30 s** vs a measured plant
  response of **~0.03–0.05 s**. The lookahead buffer is probably tuned for whole-vehicle
  latency (sensing+plan), not actuator delay — flag for review before trusting the 0.05 s fit.
