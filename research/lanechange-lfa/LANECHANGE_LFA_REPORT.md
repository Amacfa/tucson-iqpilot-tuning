# Lane-change wobble + "Check LFA System" warning — raw-CAN analysis and v3 candidate

Data: 59 post-install segments (routes 0x24–0x2a, v2 tune, release 3736edc), raw CAN exported on-device
(`analysis/lfa/export_can_lfa.py`, addresses 234 MDPS / 298 LFA / 80 LKAS / 480 LFAHDA_CLUSTER on all buses, plus
`sendcan`, `selfdriveState`, `carState`, `pandaStates`, `onroadEvents`). Nothing was installed on the comma.
Segment `00000029--af0e2ac1ba--9` is truncated on the device and was not used.

## 1. Lane-change wobble — what the data shows

Worked example: route 0x26 seg 6, 18.6 m/s (42 mph). Driver blinker 36.06 s → "Steer Right" prompt → driver nudges
(steerOverride 38.40 s) → "Changing Lanes" 38.46 s → control handed back at 38.63 s → lane change ends 43.3 s.
From 43.3 s onward, on a straight road with a near-constant request, the loop sits in a **self-sustained 1.5–1.6 Hz
limit cycle**: requested lat-accel ±0.05 m/s², measured lat-accel ±0.65 m/s² (2.6 m/s² p-p), torque request ±0.4,
applied torque ±0.22 (a triangle wave — the Hyundai rate limit of 2/270 per 10 ms is engaged the whole time).
No MDPS fault bit, no panda saturation, no driver torque.

Decomposition of the feed-forward term `f` (from `controlsState.lateralControlState.torqueState`) shows `f − requested`
is a **square wave switching between −0.45 and +0.17 m/s²** in step with the error sign: that is the friction
compensation (`0.7 × 0.12 × latAccelFactor ≈ ±0.29 m/s²`), saturating because |error| > FRICTION_THRESHOLD (0.3).
The P term at this speed is `0.8 × KP_INTERP(18.6) = 1.37` (upstream openpilot uses ~1.0), contributing ±1 m/s².

Plant estimate (closed-loop cross-spectrum, applied torque → measured lat-accel, 195 s at 15–22 m/s): coherent only
at 1.4–1.8 Hz with |H| ≈ 4.6 m/s² per unit torque (≈1.2× the DC gain of ~3.8) and −105° phase — i.e. the steering
system is mildly under-damped near 1.5–1.9 Hz and the loop gain there is ≈ 1.37 × 4.6 / 3.48 ≈ 1.8 before the friction
relay is added. With the actuator rate limiter adding phase lag once a big transient (the hand-back) saturates it,
this is a textbook relay + rate-limit limit cycle: small disturbances decay, a large kick (lane change hand-back,
curve exit) locks it in. This is consistent with why it shows up after lane changes and not on gentle straights.

Baseline (Teal-era) drives have the same mechanism at a similar rate (16 % of hand-backs vs 12 % for v2), so the
lane-change wobble is not caused by v2; v2 changed how it feels (lower friction relay with lower torque per
lat-accel), not whether it happens.

### Directional closed-loop sim (`analysis/wobble/sim_handback.py`)

Plant: 2nd-order K=3.8, ωn=12 rad/s, ζ=0.45, delay 0.08 s + Hyundai rate limiter; controller: replica of v2
(speed-scheduled P×0.8, KI, friction relay ×0.7, 0.3 s request-buffer FF, JERK_GAIN); excitation: the real requested
lat-accel from the 0x26-6 lane change, driver-override interval taken from data. It reproduces the sustained
post-hand-back limit cycle for v2 (~60 % of the real amplitude — directional, not proof).

| variant (43.3–47.5 s, straight after lane change) | meas. lat-accel RMS | 1–3 Hz fraction | tracking RMS |
|---|---|---|---|
| real drive | 0.45 | — | — |
| v2 as installed | 0.29 | 0.93 | 0.29 |
| A: P ×0.6 above 15 m/s | 0.27 | 0.89 | 0.26 |
| B: friction on low-passed error (τ 0.3 s) | 0.29 | 0.92 | 0.28 |
| **C: A + B** | **0.13** | **0.70** | **0.12** |
| C + friction ×0.5 | 0.08 | 0.31 | 0.06 |
| D: hand-back gain ramp 0.4→1 over 1.5 s | 0.29 | 0.93 | 0.29 |
| E: extra request rate limit 1.0/s | 0.32 | 0.96 | 0.32 |
| plant ζ 0.45→0.8 (proxy: more MDPS damping), v2 unchanged | 0.11 | 0.65 | 0.11 |

Either A or B alone is not enough — the limit cycle is nonlinear and only breaks when both the P loop gain and the
friction relay are reduced at the oscillation frequency. Hand-back-only ramps (D) do not help because the cycle
sustains itself long after the ramp ends. A slower request rate limit (E) makes it worse (more phase lag). C is
robust across plant variants (ζ 0.35–0.55, delay 0.06–0.10 s); it does not fully suppress the cycle for the most
under-damped/most delayed plant tried.

### v3 candidate (offline only, NOT installed): `patches/v2_to_v3.patch`

- `HANDBACK_TUNE["HYUNDAI_TUCSON_4TH_GEN"]`: P gain multiplied by 1.0→0.6 between 12 and 15 m/s (unchanged below
  27 mph, −40 % from 34 mph up; at 42 mph P goes 1.37 → 0.82, close to upstream openpilot's 1.0).
- friction compensation driven by a 0.3 s low-passed error instead of the raw error (the desired-jerk part is
  unchanged), reset when inactive.
- No change to feed-forward, request buffer, safety limits, rate limits, or longitudinal.

Expected trade-off: slower correction of slow lane drift at highway speed (I term and feed-forward carry it);
the sim shows tracking RMS improving because the oscillation dominates. Needs supervised A/B on the same
lane-change/curve-exit route before any claim.

### Plant-side hypothesis (needs its own A/B, not in v3)

The stock camera sends `LFA.DampingGain = 100` at all times (idle and while it steers). IQ sends 100 when inactive
and **0 while actively steering** (`hyundaicanfd.py`); upstream openpilot never sets this byte (0). If this byte does
what its IQ name suggests, IQ removes MDPS-side damping exactly when it steers, which would explain a lightly-damped
1.5–1.9 Hz steering mode. Sim: raising plant ζ 0.45→0.8 suppresses the cycle with no controller change. The
semantics are unverified — this is a hypothesis. Test: one drive with `DampingGain=100` while active, same route.
Panda safety does not check this byte (torque/steer-req only), so native limits are untouched.

## 2. "Check Lane Following Assist (LFA) System" — what the raw CAN shows

Across the 7 v2 routes there are **66 events (≈9 per drive)**, each exactly 2.0 s long, at irregular intervals
(3–200 s), where the **camera** (LFA 0x12a on the camera bus) switches `LKA_MODE 1→7, FCA_SYSWARN 0→1, VALUE63 0→15,
LKA_ICON→0` and simultaneously requests a cluster popup `LFAHDA_CLUSTER.HDA_InfoPUDis = 3` with the LFA symbol off.
IQ's cluster message copies `HDA_InfoPUDis` through to the dash (`sendcan` 0x1e0 shows the same 3), which is the
yellow message.

What it is **not** correlated with (66/66 events):
- MDPS `LKA_FAULT` / `LFA2_FAULT`: always 0 → not a steering-ECU fault, and why the app logs zero steer faults.
- IQ state: 33 disabled / 26 enabled / 7 overriding; IQ `STEER_REQ` 1 in 38, 0 in 28.
- Speed: 0 (in park, seatbelt off, before the drive) up to 21 m/s; median 6 m/s.
- Driver torque, torque request magnitude, frame timing (no gaps on MDPS relay / LFA / cluster at 50 ms resolution
  before events), panda `safetyTxBlocked`/`safetyRxInvalid` counters.

So the warning is generated by the **forward camera's own periodic self-check**, independent of what IQ is steering
at that moment, and IQ forwards the popup. It cannot be tied to the arming fix or the steering tune.

Structural differences that are candidates for what the camera/MDPS objects to (all present in stock IQ and in
Teal's version alike):

| field in LFA 0x12a | stock camera sends | IQ sends to MDPS |
|---|---|---|
| LKA_MODE | 1 | 2 |
| HAS_LANE_SAFETY | 1 | 0 |
| NEW_SIGNAL_1 | 8 | 0 |
| LKA_ACTIVE | 3 (when camera thinks it steers) | 0 |
| DampingGain | 100 | 0 while steering / 100 idle |

Note the camera itself has `STEER_REQ=1` for long stretches (it believes it is lane-keeping, because IQ mirrors
its STEER_REQ back in the relayed MDPS `LKA_ACTIVE`), while its torque request is only ±44 (of 1024).

### What would settle it (cheapest first)

1. **Native check**: one 10–15 min drive with the comma disconnected (or offroad) on the same roads. If the yellow
   message still appears ≈9 times, it is the car/camera (a dealer/camera-calibration matter), not IQ.
2. If it does not appear natively: A/B IQ's LFA fields toward the camera's (`LKA_MODE 1`, `HAS_LANE_SAFETY 1`,
   `NEW_SIGNAL_1 8`, `DampingGain 100`), one at a time, same route, counting events with `analysis/lfa/warn_scan.py`.
3. Cosmetic only (not recommended without 1–2): stop copying `HDA_InfoPUDis` when the camera is in the
   `LKA_MODE=7` state — hides the popup, does not remove whatever the camera is flagging.

## Files

- `analysis/lfa/export_can_lfa.py`, `run_export_all.sh` — bounded on-device export (raw CAN + app state).
- `analysis/lfa/decode.py`, `status_changes.py`, `warn_scan.py`, `warn_context.py` — decode/scan tools; `warn_events.json`.
- `analysis/wobble/fit_plant.py`, `sim_handback.py` — plant estimate and hand-back closed-loop sim.
- `patches/v2_to_v3.patch` — v3 candidate against the installed v2 `latcontrol_torque.py` (offline only).
