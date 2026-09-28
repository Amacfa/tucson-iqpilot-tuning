# Tune v2 — second batch of drives (routes 0x28–0x2a)

Retrieved 2026-09-28 21:27 UTC: 29 new segments on release `3736edc`, 28 exported
(segment `00000029--…--9` failed to pull/export and is recorded as a limitation, not repaired).
Installed files verified byte-identical to the v2 tune package and the arming package
(the hourly checker's earlier "MISMATCH" lines were stale pre-rebase manifests; fixed).

Post-install totals (drives 24–2a): 0.51 active-hr steering, 0.40 long-hr.
Baseline: 2.42 active-hr, 1.45 long-hr (older release, so long results are confounded
by the release's new speed-error PID).

## Steering

| metric | baseline | drive 1 (v1 filter) | v2 routes 25–27 | v2 routes 28–2a |
|---|---|---|---|---|
| curve exits (clean) | 175 | 6 | 17 | 22 |
| torque 0.5–3 Hz fraction | 0.342 | 0.751 | 0.395 | **0.362** |
| lat-accel 0.5–3 Hz fraction | 0.216 | 0.660 | 0.240 | **0.190** |
| steering-angle p2p (deg) | 27.0 | 35.8 | 28.3 | **21.8** |
| torque band RMS ×270 | 6.41 | 18.05 | 6.66 | **6.31** |

Post-curve wobble is at (or slightly below) baseline on both v2 batches. The 60 ms
measurement filter removal is confirmed as the fix (3 drives, 22 exits).

Mid-speed (15–20 m/s) oscillation episodes (3 s windows, tracking-error 0.5–3 Hz
fraction > 0.6, amplitude > 0.4 m/s², no override):

- baseline: 22.6 / hr at 15–20 m/s, 21.1 / hr at 20+
- v2 25–27: 2 episodes (route 26, one segment) in 0.05 hr
- v2 28–2a: **0 episodes** in 0.073 hr at 15–20 m/s and 0.025 hr at 20+ (baseline rate predicts ~2)

Not enough exposure to call the 41 mph wobble gone; it is not recurring at baseline rate.

Tracking (actual/requested lat-accel), all post-install: 5–10: 0.97, 10–15: 1.16,
15–20: 1.09, 20–25: 1.08 (baseline 1.00 / 1.16 / 1.19 / 1.14, 25–40: 1.30).
P-opposing-FF fraction 0.634 vs 0.683 baseline. Saturation 0.048% vs 0.037%.
Torque dither RMS ×270 remains ~0.1–0.4 higher than baseline at every speed bin
(2.53/2.01/1.94/1.88 vs 2.14/1.86/1.89/1.82) — small, consistent with the live
torque learner still relearning after the release reset.

Faults/events, routes 28–2a: `steerFaultTemporary` 0, `steerFaultPermanent` 0, no
LKA/steer-unavailable, no `steerSaturated`, no `accFaulted`, no FCW. Lateral active
while moving: 0.90 / 0.97 / 0.90. `commIssue`/`selfdriveInitializing` clusters are
boot-time only. `cruiseMismatch` has no alert (commented out in device source).

## Longitudinal (still confounded by release change)

| metric | baseline (1.45 hr) | v2 all (0.39 hr) |
|---|---|---|
| clean launches (no pedal) | 12 | 4 |
| launch: cmd peak / actual peak | 1.91 / 1.83 | 1.99 / 2.80 |
| launch: time to 1 m/s | 0.42 s | 0.17 s |
| launch mean |jerk| | 1.37 | 2.05 |
| clean stops | 21 | 13 |
| stop: last-1 s cmd / actual | −0.50 / −0.20 | −0.66 / −0.13 |
| stop: min accel in last 3 s | −0.47 | −0.88 |
| stop mean |jerk| | 0.83 | 1.14 |
| gas overrides / long-hr | 54.6 | 88.2 |
| brake overrides / long-hr | 29.1 | 41.5 |
| jerk RMS (moving) | 4.08 | 4.46 |

Personality: routes 28–2a ran entirely on `relaxed`; 25–27 mostly `aggressive`;
baseline release did not log personality.

Reading: launches are noticeably punchier (actual peak +50%, 2.5× faster to 1 m/s) —
that is the signature of the jerk-up floor/boost candidate and/or the new release's
speed-error PID. Stops brake harder in the final 3 s and end with more jerk than
baseline. Gas/brake override rates are up. None of this can be attributed to the
candidate vs the release change without an A/B on the same release, and 4 launches /
13 stops is thin.

## Decision

- No change to the comma. v2 stays installed.
- Steering: no further steering candidate is justified; remaining item is confirming the
  15–20 m/s oscillation rate over more exposure and letting the torque learner settle.
- Longitudinal: the next drive should give feel feedback on launches (too eager?) and
  the last car-length of stops (too abrupt?). If "too eager"/"too abrupt", the
  reviewable options are (a) roll back the jerk-up candidate alone (its package is
  independent) to isolate the release effect, or (b) a stopping-taper proposal. Neither
  is proposed yet.
