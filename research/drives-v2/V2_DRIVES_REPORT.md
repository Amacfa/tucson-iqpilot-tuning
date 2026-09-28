# Tune v2 (filter removed) — first physical A/B, routes 25–27

Release 3736edc, tune v2 + arming fix + fingerprint candidate installed; IQHkgReducedTorqueFeedback=1.
Three drives, 25 segments (1500 s wall), ~14 min lateral-active without driver override, ~10 min long-active.

## Steering faults / warnings
- steerFaultTemporary = 0, steerFaultPermanent = 0 across all three drives (and drive 1).
- No LKA / steering-unavailable / steerSaturated / accFaulted events. No steering-related UI alert
  (alerts seen: lane-change prompts, driver-attention, "Brake Pedal Held", personality change, reverse).
- Lateral engagement while moving: 0.71–0.89 of moving time (baseline 0.80) — the SET/RES-only arming is not
  costing engagement.
- `cruiseMismatch` is high in the event counts but is benign here: on this fork it is raised whenever the car's
  cruise is on and `pcmCruise` is false (openpilot long), and its alert is commented out in events.py.
- Boot-time cluster (commIssue/posenetInvalid/paramsdTemporaryError/canError, ~7 s after start) still present
  in every drive — not steering; same as drive 1.

## Post-curve wobble (curve exits, 4 s window, excludes any override / lateral drop)
| group | exits | torque 0.5–3 Hz frac | latAccel 0.5–3 Hz frac | steer p2p deg | torque sign changes | band RMS x270 |
|---|---|---|---|---|---|---|
| baseline (pre-install) | 175 | 0.342 | 0.216 | 27.0 | 4.6 | 6.41 |
| drive 1 (v1, 60 ms filter) | 6 | 0.751 | 0.660 | 35.8 | 6.5 | 18.05 |
| v2 (routes 25–27) | 17 | 0.395 | 0.240 | 28.3 | 4.5 | 6.66 |

By speed (v2 vs baseline, torque frac / band RMS): 5–10 m/s 0.40/7.7 vs 0.45/8.2; 10–15 m/s 0.35/5.6 vs 0.28/5.0;
15–20 m/s 0.32/4.8 vs 0.23/3.7. Route 26 was the noisiest (0.50/8.8, 6 exits), route 25 (10 exits) at baseline.

Conclusion: removing the measurement filter took the post-curve wobble from ~2.8x baseline (drive 1) back to
baseline level (+15% on torque band fraction, within the spread of individual drives). The 60 ms filter was the cause.

## Lat-accel tracking (actual/requested, |requested|>0.3, no override)
| speed m/s | baseline | drive 1 | route 25 | route 26 | route 27 |
|---|---|---|---|---|---|
| 5–10 | 1.00 | 0.94 | 0.99 | 1.01 | 1.03 |
| 10–15 | 1.16 | 1.07 | 0.99 | 1.11 | 1.12 |
| 15–20 | 1.19 | — | 1.06 | 1.07 | 1.19 |
| 20–25 | 1.14 | — | 1.11 | 1.11 | — |

The speed-scheduled latAccelFactor moved 10–20 m/s tracking closer to 1.0 (was +16–19% over-response in
baseline; now +0–12%). Still slightly hot at 15–25 m/s; the learner is not yet valid (LiveTorqueParameters reset by
the release update; totalBucketPoints 148 → 3334 over these drives, valid=False), so friction is still the fixed 0.12.

## Torque dither (RMS of per-frame torque delta x270, no override)
5–10: 3.2 (v2) vs baseline metric in hourly report 2.1→2.5; 10–15: 2.9 vs 1.9→2.0; 15–20: 2.0–2.3 vs 1.9→2.0;
20–25: 1.7–2.0 vs 1.8. Slightly higher below 15 m/s, unchanged above. P-opposing-FF fraction 0.54–0.59 vs 0.68
baseline (less fighting between correction and feed-forward).

## Mid-speed oscillation episodes (3 s windows, 0.5–3 Hz fraction of tracking error > 0.6 and amplitude > 0.4 m/s²)
| group | 5–10 | 10–15 | 15–20 | 20+ | (episodes per lateral-active hour) |
|---|---|---|---|---|---|
| baseline | 0 | 1.8 | 22.6 | 21.1 | (1.47 h) |
| drive 1 | 92 | 63 | 0 | — | (0.03 h) |
| v2 | 0 | 0 | 40 (2 episodes / 0.05 h) | 0 | (0.12 h) |

Both v2 episodes are one event: route 26 seg 6, t≈40–46 s, 18–19 m/s (~41 mph), straight-ish road (desired
latAccel ≈ −0.4 flat), actual latAccel swinging ±0.6–1.3 m/s² at ~1.5 Hz, steering angle ±8°, P term ±1.0, no
lane change, no driver input. This is the same 35–45 mph oscillation class that exists in the baseline drives at a
similar rate, not something v2 introduced — but it is the largest remaining smoothness defect and the next target.

Model note: the first-order plant used in SIM_REPORT.md (T≈0.6–0.8 s) predicts >85° phase margin at 18 m/s even with
0.2 s extra delay, so it cannot reproduce a 1.5 Hz limit cycle; torque→latAccel cross-correlation lag is 0.17 s at
9–13 m/s but 0.63 s at 15–20 m/s. A higher-order/rate-limited plant fitted on 35–45 mph data is needed before any
mid-speed KP/lead change can be validated offline. Not installed; no candidate proposed yet.

## Longitudinal
Only ~10 min long-active over three drives, almost all in "aggressive" personality (baseline drives carry no
personality tag), 1 clean launch and 0 clean stops per drive. Not enough to judge the jerk_u candidate or a stopping
taper. Gas/brake override rates (39–94 / 0–41 per hour) are inflated by short neighborhood drives; no change proposed.

## Decision
- Keep v2 as installed. No new install.
- Next offline work: fit a plant that reproduces the 41 mph episode (route 26 seg 6) and evaluate a 15–25 m/s KP
  reduction / lead term against it; needs more 35–45 mph steady-road data.
- Next drive request: 15–20 min with as much 35–45 mph steady road as practical, engaged with SET/RES, plus a few
  full stops and launches with IQ long active (so the long candidate can finally be judged).

Scripts: wobble_v2.py, osc_episodes.py, extract_frames.py (this directory); data v2_frames.npz, exits_v2.json,
osc_episodes.json.
