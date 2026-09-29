# Longitudinal — offline analysis of the 3736edc drives (routes 24–2a, ~15 min IQ-long)

No car time used. Data: existing v2 exports (`drives/export/000000{24..2a}*`), script
`analyze_speed_pid.py`.

## What changed in the release (457ea8e → 3736edc), longitudinal only
`git diff` on the comma: `smooth_stops.py` unchanged; `longitudinal_planner.py` adds an
opt-in `IQGasOverrideBoost` (off here); `longcontrol.py` switches the Hyundai PID error from
`aTarget - aEgo` to `speeds[0] - vEgo` (kp = 1, ki = 0, kf = 1). So on this release
`accel_cmd = aTarget + 1.0 * (v_plan[0] - vEgo)`.

## 1. The speed-error P term is small — not the cause of the punchier feel
Reconstructed as `actuators.accel - longitudinalPlan.aTarget` in PID state (92k frames, 920 s):

| speed | P rms (m/s²) | mean | aTarget rms |
|---|---|---|---|
| 0–1 m/s | 0.22 | −0.09 | 0.65 |
| 1–3 | 0.17 | −0.09 | 0.89 |
| 3–8 | 0.12 | +0.03 | 1.06 |
| 8–15 | 0.10 | +0.01 | 0.66 |
| 15–40 | 0.08 | −0.01 | 0.34 |

Median |P|/|command| = 17 %. The old accel-error term would have been ~2× larger (rms 0.23)
and only weakly correlated (r = 0.38), so the release change mostly *removed* aEgo noise from
the command. Nothing to tune here.

## 2. Launches: the car delivers 1.3–2.2× the commanded acceleration
Six clean launches (no pedal, PID state, first 2 s from 0.3 m/s):

| seg | aTarget mean | cmd peak | aEgo peak |
|---|---|---|---|
| 26-8 | 1.56 | 2.00 | 3.04 |
| 28-5 | 1.44 | 1.76 | 2.20 |
| 2a-3 | 1.51 | 2.00 | 4.31 |
| 2a-5 | 1.30 | 1.92 | 3.79 |
| 26-6 / 29-2 (gentle) | 0.11 / 0.39 | 0.22 / 0.60 | 0.68 / 0.91 |

Baseline drives (457ea8e, no jerk change): cmd peak 1.91 / actual 1.83 — the car used to
track the command. Now actual overshoots command by up to 2.3 m/s². The command itself is
not higher (aTarget ≈ 1.5, P ≤ +0.5); what changed in how the *car* realises the command is
the SCC upper-jerk limit I raised in candidate L1: `jerk_u = max(1.0 + 2·(accel−1), 2·mpc_jerk)`
→ 3.0 m/s³ at a 2.0 command, vs ≤ ~1 m/s³ before. The Tucson's SCC evidently uses that jerk
allowance as a ramp *rate* and overshoots the accel target at low speed. Conclusion: the
"launches too eager" feel is most likely my L1 boost, not the release. (aEgo is a wheel-speed
derivative and reads high on launch, but the baseline measure was the same, so the ratio
change is real.)

## 3. Stops: planner-driven, unchanged code
In the last 3 s of 14 stops the command minimum equals the planner aTarget minimum within
0.1 m/s² in 12/14 (P contribution −0.03…−0.24). `smooth_stops.py` is byte-identical between
releases, so the firmer stops come from the planner/model in the new release (and routes
28–2a ran on `relaxed` personality, 25–27 on `aggressive`), not from anything installed.
The earlier crawl finding (STOP_TAPER.md, candidate S1) still stands but is now lower priority
than the launch overshoot.

## Proposal L1b (offline, not installed) — `L1b_jerk_u_launch_cap.patch`
Keep the 1.0 m/s³ floor (this fixed the hesitation) but halve the raw-request boost and cap
the upper jerk to 1.5 m/s³ below 3 m/s, ramping to the release cap by 8 m/s:

```python
jerk_u_cap = np.interp(vEgo, [3.0, 8.0], [1.5, jerk_max_u])
jerk_u_raw = clip(1.0 + 1.0*max(0, accel-1.0), 1.0, jerk_u_cap)
jerk_u_mpc = clip(2.0*mpc_jerk, 1.0, jerk_u_cap)
```

Expected: launch ramp limited to ~1.5 m/s³ (0→1.5 m/s² in 1 s instead of 0.5 s), so the SCC
has no room to overshoot; above 8 m/s behaviour identical to today (no highway change).
Native `jerk_l` (braking authority) untouched. Cannot be validated offline — needs the
car-side response, i.e. one normal drive with a couple of stop-and-go launches; success =
aEgo peak / cmd peak back near 1.0 and time-to-1 m/s between the baseline 0.42 s and today's
0.17 s.

Nothing installed. Requires the same package flow as v2 (carcontroller.py target).
