# Post-curve wobble analysis — route 00000024--f0646026ab (post-install, 3736edc)

Drive: 5 segments, 300 s, ~0.046 active-hr, IQHkgReducedTorqueFeedback=1.
All three rebased packages installed+verified. Analysis over
`/home/ubuntu/tucson/drives/export/00000024--f0646026ab--{0..4}.jsonl.gz`.

## 1. Faults / warnings timeline

**No steering faults of any kind in this drive.**

- `sft` (steerFaultTemporary): 0 frames nonzero in all 5 segs.
- `sfp` (steerFaultPermanent): 0 frames nonzero.
- `ldw`, steer-saturated flag `sat`: no `steerSaturated` event.
- `avail` (steerAvailable): lat-active frames all `avail=1` — no dropouts.
- Unique onroadEvents (excl. iqOnroadEvents shells): gasPressedOverride ×167,
  steerOverride ×95, cruiseMismatch ×61, wrongGear ×9 (seg4, parking),
  selfdriveInitializing ×7 (seg0 boot), commIssue ×7 + commIssueAvgFreq ×2 +
  posenetInvalid ×6 + paramsdTemporaryError ×6 (all clustered seg0 t≈7.4–10.4,
  i.e. the just-booted startup transient — CAN bus still filling), canBusMissing ×2
  and reverseGear/preEnableStandstill (seg4 parking), seatbeltNotLatched ×1,
  canError ×1 (seg0 t=8.9), buttonEnable ×2, buttonCancel ×1.
- **Zero steerTempUnavailable / steerTempUnavailableSilent / LKA-warning-type events**
  — consistent with the pipeline report. Alex's "errors still appeared" most likely
  refers to the subjective dash/icon behavior OR the commIssue/paramsd startup
  cluster (seg0 t≈7–10s would surface a transient comma "initialization"
  alert on-screen), not a steering-fault event.
- Arming code in swaglog: `grep` of `/data/log/swaglog.0000003522..3531`
  (files covering 04:36–04:39Z drive) found **zero** lines matching
  `steering_fault|iq_controls_layer|tucson|invalidat|rearm|arming` — the arming
  layer logged nothing; no steering-fault recovery or SET/RES rearm events fired.

## 2. Post-curve wobble metric

Curve exit = |dla| > 0.8 falling below 0.3 while lat-active; 4 s window after.
Band = 0.5–3 Hz fraction of FFT energy (`postcurve_wobble.py`).

| epoch | speed | n | band% tq | band% ala | band% ang | ang p2p (deg) | tq sign-changes | band-RMS tq ×270 |
|---|---|---|---|---|---|---|---|---|
| pre  | 5–10  | 121 | 0.445 | 0.204 | 0.211 | 47.0 | 5.6 | 10.87 |
| pre  | 10–15 | 80  | 0.285 | 0.171 | 0.132 | 29.8 | 3.4 | 7.84 |
| pre  | 15–20 | 65  | 0.261 | 0.159 | 0.143 | 13.2 | 2.6 | 4.41 |
| post | 5–10  | 2   | 0.690 | 0.254 | 0.290 | 42.4 | 4.0 | 13.36 |
| post | 10–15 | 3   | 0.761 | 0.622 | 0.616 | 25.8 | 6.7 | 14.10 |

Post-install exits show a **much larger share of torque/latAccel/angle energy in the
0.5–3 Hz band** (0.62–0.95 vs ~0.13–0.30 at 10–15 m/s) and ~1.8× band-RMS torque —
i.e. real post-curve oscillation, consistent with "wobble after a turn". Caveat:
only 7 post exits (0.046 hr) vs 315 pre (2.4 hr); several post exits are at v≈5–11
with ang p2p 20–43° (sharp maneuvers, some steerOverride-adjacent).

Worst exits: seg3 t=37.92 (v=4.9, f_tq 0.92, ang p2p 42°), seg3 t=8.64 (f_tq 0.79),
seg2 t=51.84 (v=11, f_tq 0.98, 9 sign changes). Snippets:
`/home/ubuntu/tucson/analysis/wobble/snippets.txt` (t/v/dla/ala/tqo/p/i/f/out/ang/rate).
At seg3 t=37.9 the snippet shows P term dominating (p≈1.4–2.4) while `out`
oscillates ~±0.05–0.17 and `rate` (steer rate cmd) swings 0→240 — the P term is
fighting the LP'd measurement error hard at curve exit; `i` stays pinned 0.038.

## 3. Tune active?

- CarParams this drive: `latAccelFactor=2.96017`, `friction=0.12` (liveTorqueParams
  filtered=0.12, useParams=True) — pre-install baseline was friction **0.10875**.
  The 0.12 is exactly the tune's params.toml value → tune's params are live.
- ff/dla medians post vs pre (same bins): post v4–10 ≈ 1.03–1.12, v10–15 ≈ 0.60–0.80;
  pre v4–10 ≈ 0.19–0.47, v10–15 ≈ 0.01–0.50, v15–25 ≈ 0.63–0.80. Post FF is clearly
  stronger at low speed — consistent with the speed-scheduled latAccelFactor/FF
  table (2.95/3.35/3.70) rather than stock.
- Measurement smoothing: mean|Δala| vs mean|Δ(v²·curvature)| ratio = 0.70 in seg3
  (filtered faster); segs 1–2 ≈ 1.3–1.4 (ala includes model/noise path — LP is on
  the feedback used by P, not necessarily the logged ala). Combined with the friction
  and FF evidence the tune controller is running.
- `steerActuatorDelay=0.1`, `steerLimitTimer=0.4`, `steerControlType=torque`,
  `alternativeExperience=1024`, fingerprint HYUNDAI_TUCSON_4TH_GEN — all identical
  to baseline. **No CarParams change in 3736edc** that would explain wobble.
- lateralTorqueParameters: `totalBucketPoints=0` at first log (fresh after update;
  baseline had 3909, calPerc 48) — live-torque learner was reset by the update and
  had ~0 calibration during this drive. useParams=True means params fallback
  (2.96017/0.12) is what's used — fine.

## 4. New-release torque-path changes (core_diff.txt)

- **SteerShortfallCheck** (new, selfdrived/helpers.py): fires `steerSaturated` when
  |desired latAccel| > 1.0 and actual persistently falls short (>0.5 or 25% shortfall)
  for ≥1 s at v>5, using the new `lateralDelay` message (207 msgs logged — service
  present). It **did not fire** in this drive (no steerSaturated events) despite the
  wobble — the exits satisfy shortfall for <1 s each.
- The old `steerSaturated` logic (undershooting+turning+lac.saturated) was removed;
  actual latAccel now prefers pose-derived `v·yaw_rate` when posenetOK.
- `lac` lateralControlState source unchanged (torque state from controlsState);
  `EnableCurvatureController` is VW-only; no changes to LatControlTorque selection
  or PID gains in the controls diff. Nothing else in the diff runs in the Hyundai
  torque path.

## Interpretation for the report (facts only)

Subjective "wobble after a turn" matches elevated 0.5–3 Hz energy at curve exits
vs the pre-install fleet baseline; no faults/events back a "fault" reading. The
startup commIssue/paramsd cluster is the only visible on-screen "error" candidate.
Band-RMS torque ×270 post (13–14) is ~1.7× pre at 10–15 m/s — but n=3–5 exits and
the post drive is almost all low-speed/tight (high ang p2p). No recommendation.
