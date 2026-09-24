# Stopping behaviour on the Tucson — analysis of the existing 28 clean stops

Source: `all_frames.npy` (pre-install drives), stops where longitudinal control
was active for the full 4 s before standstill with no gas/brake input.
Current device code path (IQ release 457ea8e): `IQForceStops=1`, so
`SmoothStopController.settle()` governs the command while `shouldStop` is set,
then `LongControl` ramps to `stopAccel=-2.0` at `stoppingDecelRate=1.0 m/s^3`
after standstill. `CanfdStopRetry=0` (stopping experiment off).

## What the code does

```
landing  = 0.25 + (0.80 - 0.25) * min(v/1.0, 1.0)     # STOP_KISS_DECEL, SETTLE_DECEL, TAPER_SPEED
a_settle = -landing  (further limited by lead gap, minus 0.5 m/s^3 * stall time)
cmd      = min(a_settle, a_target)  rate-limited at 2.5 m/s^3
```

## What the data shows

| speed band (m/s) | command median | actual median |
|---|---|---|
| 1.0–1.5 | −0.70 | −0.38 |
| 0.5–1.0 | −0.52 | −0.17 |
| 0.25–0.5 | −0.47 | −0.27 |
| 0.0–0.25 | −0.37 | −0.26 |

- Command tracks the settle curve almost exactly (command − curve: median +0.04 m/s^2),
  i.e. the smooth-stop controller, not the planner, sets the last metre.
- Below 1 m/s the car delivers only 30–60 % of the commanded deceleration:
  the Tucson's creep torque is eating most of a −0.5 m/s^2 request.
- Result: the last 1 m/s (walking pace) takes ≥ 4 s in 24 of 28 stops
  (the 4 s window did not even contain the 1 m/s crossing in 18 of them),
  and 46 % of stops contain a ≥ 0.5 s stall where speed stops falling and
  the anti-creep term has to ramp the brake up.
- The final "nod": minimum actual decel in the last second is −0.35 m/s^2 median,
  −0.56 at the 10th percentile. That is mild; the two hard cases
  (−2.5, −2.0) were genuinely short stops, not taper problems.
- Post-standstill hold ramp (−0.33 → −1.32 in 1 s) is invisible in aEgo
  (car is stopped), so no evidence either way on `stoppingDecelRateOverride`.

Conclusion: the perceived stopping issue on this car is a long, hesitant
crawl caused by creep torque overpowering the gentle settle curve — not a
harsh landing. The kiss value (0.25) is fine; the approach is too soft.

## Candidate S1 (proposal only — not installed, needs an A/B drive)

`iqpilot/selfdrive/controls/lib/smooth_stops.py`

```diff
-SETTLE_DECEL = 0.80
-TAPER_SPEED = 1.0
+SETTLE_DECEL = 1.00
+TAPER_SPEED = 0.6
```

Effect: hold about −1.0 m/s^2 commanded (≈ −0.6 delivered on this car) down to
0.6 m/s, then taper to the same −0.25 kiss over the last 0.6 m/s. Expected
crawl from 1 m/s to standstill ≈ 1.5–2 s instead of ≥ 4 s, with the same
final landing. Lead-gap limiting and anti-creep are unchanged, so it
cannot land closer to a lead than today.

Risk: a firmer approach makes the final kiss slightly more noticeable if
the creep torque drops off faster than the taper. Mitigation if felt:
`STOP_KISS_DECEL 0.25 → 0.20`.

Not proposed: `stoppingDecelRateOverride` (no measurable evidence),
`stopAccel` (native hold value), anything in `hyundai/stopping.py` (feature off).

Validation plan: after the next drive compare, per stop, time from 1 m/s to
standstill, stall time, min actual decel in the last second, and whether a
lead was present (new v2 export carries `dRel`/`shouldStop`/`aTarget`).
