# Tucson deep research: steering + acceleration tuning candidates

Data: all 36 recorded routes on the comma (1.467 M control frames, 100 Hz). Nothing on the device was
changed. Source of truth: `export/*.jsonl.gz` -> `all_frames.npy`; scripts `analyze_long.py`,
`analyze_long2.py`, `analyze_steer2.py`. Route IDs are the 8-hex-digit prefixes.

Usage split: long-active 1.45 h, lateral-only (AOL) 1.2 h, lateral active with no driver torque 2.16 h.

## A. Steering

### A1. Plant gain rises strongly with speed; one static factor cannot fit all speeds
Steady-state frames only (torque steady 0.5 s, |steering rate| < 3 deg/s), lat-accel per unit torque
fraction (sign inverted in this stack; magnitudes shown):

| speed m/s | n | OLS slope | dead-band fit (db, k) |
|---|---|---|---|
| 5-8 | 10.5k | 3.1 | 0.03, 3.7 |
| 8-12 | 18k | 4.3 | 0.03, 5.3 |
| 12-16 | 27.7k | 4.5 | 0.03, 5.7 |
| 16-20 | 17.9k | 6.1 | 0.03, 7.5 |
| 20-25 | 2.8k | 7.1 | 0.03, 8.9 |
| 25-40 | 1.1k | 5.0 (thin) | 0.14, 9.2 |

Closed-loop consequence, actual vs desired lat-accel (desired delayed 0.3 s), active, no driver torque:

| speed | |desired| 0.1-0.3 | 0.3-0.7 | 0.7-1.2 | 1.2-2.0 | 2-4 |
|---|---|---|---|---|---|
| 5-10 | 0.78 | 0.91 | 0.92 | 1.00 | 0.96 |
| 10-15 | 0.84 | 1.09 | 1.13 | 1.17 | 1.09 |
| 15-20 | 0.83 | 1.09 | 1.17 | 1.12 | 1.18 |
| 20-25 | 0.92 | 1.11 | 1.14 | 1.10 | - |
| 25-40 | 0.84 | 1.24 | - | - | - |

Controller terms confirm it: at >= 10 m/s the P term opposes the feed-forward 78-85 % of the time with
mean P ~ -0.25..-0.35 x F; at 5-10 m/s P *helps* FF (+0.18). Static factor 2.96 is about right at
city speed, ~12 % low at 10-25 m/s and ~25 % low above 25 m/s.

Note: the earlier all-drives report quoted an overall 3.29 fit (secant through origin over all frames).
The per-speed steady-state numbers above supersede it; the actionable quantity is the actual/desired
ratio table.

**Candidate A (already prepared)**: flat 2.96 -> 3.30. Fixes the 10-25 m/s over-response but will make
5-10 m/s under-respond further (0.9 -> ~0.8). Acceptable as a first physical A/B but not the end state.

**Candidate A2 (recommended instead of A, small code change)**: speed-indexed latAccelFactor in
`latcontrol_torque.py` (`torque_from_lateral_accel` path), e.g.
`np.interp(vEgo, [8, 15, 25], [2.95, 3.35, 3.70])`, friction 0.12. Requires the same physical A/B as A.
No delay change, no P/I change, no native-limit change.

### A2. Small requests under-respond everywhere (0.78-0.92 at |desired| 0.1-0.3)
The runtime friction is 0.1087 x 0.7 (reduced-feedback scaling) = 0.076 torque fraction; the measured
threshold where the car starts to respond is 0.03-0.10 depending on the fit. Slightly raising friction
(0.12 in Candidate A; 0.13-0.14 is defensible) improves lane-centre nudges. Going higher risks dither.

### A3. Residual torque dither is steering-angle quantisation through P (now quantified)
Steering angle arrives in 0.1 deg steps; 45 % of active frames carry a step. On those frames:
- |d actualLatAccel| median 0.006-0.015 m/s^2 (vs 0.0001 with no step),
- |dP| 0.013 (vs 0.0008),
- output torque jumps 1.35-1.9 native units (vs 0.19).
This is the whole 1.5-2 unit RMS dither found earlier. Actual lat-accel high-frequency energy is
negligible, so the car does not feel it as oscillation, but it is what the EPS "buzz" is made of.

**Candidate B (code, after A/A2 has physical data)**: first-order low-pass on the measured lat-accel
(tau ~ 0.05-0.08 s) or a 0.02-0.03 m/s^2 dead zone before P. Expected: dither gone, no tracking
change (the LP delay is < 1 frame of the 0.3 s compensated delay).

### A4. Delay is well compensated; do not touch
Cross-correlation desired -> actual lat-accel in 20 s active windows: lag 0.12 s at 5-10 m/s, 0.04 s at
10-15, 0.00 s at >= 15 m/s (corr > 0.8). The 0.3 s fallback + lookahead is doing its job.

### A5. Overrides / saturation
601 steering-override episodes (> 0.3 s), 50 % below 8 m/s, 22 % at |angle| > 60 deg: parking and
intersections, not lane keeping. Torque saturation (> 0.95) 1.1 % of active frames, all below 8 m/s;
above 15 m/s p99 |torque| is 0.33. No headroom problem at speed.

### A6. Knobs with no evidence to change
P/I gains (0.8/0.15 x 0.8), jerk look-ahead 0.19 s, jerk gain 0.3, lat-accel slew limiter, 1.2 Hz
request filter, steerLimitTimer 0.4: nothing in the data points at them. Revisit only if A/A2 + B
leave a specific symptom.

## B. Acceleration (openpilot longitudinal, CAN-FD camera-SCC, `create_acc_control_scc2` path)

### B1. Positive acceleration is under-delivered; braking is over-delivered
Command -> actual lag (cross-corr, 75 blocks): median 0.60 s (configured
`longitudinalActuatorDelay` 0.5; fine).

Step responses under long control, no pedal:
- 85 positive steps (cmd < 0.2 -> > 0.7): cmd peak 1.05, actual peak 0.74; actual/cmd over the 1-3 s
  window median **0.60** (p25 0.13).
- 97 negative steps: cmd min -1.35, actual min -1.42; ratio median **1.21**.
Steady regression by speed: slope 0.88 at 5-10 m/s, 0.76 at 15-20, 0.53 at 25+ (positive commands
largely not realised at highway speed).

Root cause (code, verified): `HyundaiJerk.make_jerk` sets the upper jerk limit
`jerk_u = min(max(0.5, mpc_jerk*2), 5)`, and `apply_accel_jerk_limit` rate-limits `aReqValue` with it
(50 Hz). When the planner's jerk is small the allowed ramp-up is **0.5 m/s^3** (2 s from 0 to 1 m/s^2),
while the lower limit has a 1.2 m/s^3 floor plus a raw-request boost. The same values are sent to the
car as `JerkUpperLimit`/`JerkLowerLimit`, so the SCC clamps the same way. This asymmetry matches the
0.60 / 1.21 measurement.

**Candidate L1 (one constant + one line in carcontroller.py)**: `jerk_u_min` 0.5 -> 1.0 and give the
upper limit the same raw-request boost as the lower one
(`jerk_u_raw = clip(1.0 + 2.0*max(0, accel-1.0), 1.0, 5.0)`). Expected: positive steps reach ~85-90 %
of command within 1-3 s, launches unchanged (they already command ~1 m/s^2 with high MPC jerk).
Physical A/B: repeat the positive-step and negative-step metrics.

### B2. Stops end with a nod
28 openpilot-controlled stops (no brake pedal): mean actual decel in the last second -0.32 .. -0.37
m/s^2, still -0.20 at standstill; min decel in the last second median -0.35, p10 -0.56; 21 % of stops
end with > 0.5 m/s^2 still on. Commanded profile: -0.6 at 4 s out, -0.5 at 1 s, -0.19 at 0 s. A
comfortable stop tapers to about -0.1 over the last 0.5 m/s.

Knobs: `iqCarParams.stoppingDecelRateOverride` and `longitudinalStoppingSpeedOverride` already exist as
params (both 0 = defaults) and the stopping-state jerk path `self.jerk = 0.25 - aEgo`. The actual
`stoppingDecelRate`/`vEgoStopping`/`stopAccel` values live in `longcontrol.py` on the device (not in
the local snapshot; the car was offline when this was written) -> read them before choosing numbers.
**Candidate L2**: taper stopping decel to ~0.15-0.2 m/s^2 in the last 0.5 m/s via the existing
override params (no code) if the defaults are the usual 0.8 m/s^3 / -2.0; confirm after reading the file.

### B3. Driver keeps overriding a hesitant planner (biggest feel item; not tunable blind)
- Gas overrides that start from long-active: 79, **55 per long-hour**; 73 % with op commanding
  < 0.05 m/s^2 at 5-20 m/s; driver then accelerates at 0.55 (p75 1.06) m/s^2 for ~5 s.
- Brake takeovers from long-active: 37, **26 per long-hour**, typically at 12 m/s with op commanding
  ~0 and the driver braking to -1.4 (p25 -2.1); only 24 % end in a stop.
- Of 193 stops in the data only 28 were left to openpilot.
This is planner/lead-following behaviour (personality, follow distance, lead reaction), not the
actuator. The exports do not contain `radarState`/`longitudinalPlan`/lead distance, so cause cannot be
assigned yet. Action: add `radarState`, `longitudinalPlan`, `modelV2.leadsV3` and the personality param
to the exporter and re-run on one ordinary drive; then tune follow distance / personality with evidence.

### B4. Error messages
- **False forward-collision warnings**: 4 "BRAKE! Risk of Collision" alerts; 3 of them at 1-3 m/s while
  openpilot itself was braking smoothly to a stop behind a lead (routes 19 x2, 22). One (route 21) was a
  real hard stop from 17 m/s (op at its -3.5 limit, driver to -4.9). Low-speed FCW gating is a
  planner-side item; note for the lead-data follow-up.
- **"Cruise Fault: Restart the Car" at shutdown**: all 8 `accFaulted` samples are in the last 0.1 s of a
  route together with `canBusMissing` (ignition off). Cosmetic; can be masked when `canBusMissing` is
  also present.
- `cruiseMismatch` (7059 samples) is silent and is the AOL lateral-only state; no user-visible alert.
- `resumeBlocked` 12 samples in 3 routes: resume pressed while blocked; expected.

### B5. Command smoothness
`actuators.accel` changes on 56 % of frames, RMS command jerk 5.6 m/s^3 (p99 18), but 92 % of its
power is below 0.2 Hz and the SCC rate limiter absorbs the rest: actual 0.5 s-smoothed jerk RMS 0.51
m/s^3. Cruise hold at > 15 m/s: actual accel std 0.22 (includes grade). Not a tuning target now.

## C. Priority order (all require explicit approval, install parked, ordinary supervised drive)
1. Arming candidate (warnings) - software-validated, uninstalled.
2. Steering A2 (or A) + friction 0.12 - physical A/B vs routes 22/23.
3. Long L1 (jerk-up authority) - physical A/B on step metrics.
4. Exporter extension + one drive -> decide follow-distance/personality (B3) and FCW gating (B4).
5. Long L2 (stop taper) after reading `longcontrol.py` on the device.
6. Steering B (measurement LP / dead zone) after A2 data.
Not recommended: delay, P/I, native limits, F1B, model changes.
