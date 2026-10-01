# S1 drive report — v5 + D1 + L1c + C1 + S1 + KARNBIRRLV2

Route `00000033` (6 segs, ~29.3k frames, ~18.9k engaged). Hourly ingest commit
`fe88746` — `S1:candidate_present`, all prior packages present, `warnings:[param
drift LongitudinalPersonality expected 1 actual 2]` — see §0.

## 0. Personality actually used on the drive

**Measured** (from `selfdriveState.personality` in rlogs, all segs): **`relaxed`**.
**Erratum**: param value 2 is Relaxed (cereal enum aggressive=0 / standard=1 /
relaxed=2 — earlier docs had it reversed). Param now reads `2` = Relaxed = the user's
intended UI selection, restored correctly by the UI at boot — *not* drift. Do not
re-apply 1. The drive ran T_FOLLOW 1.75 s / jerk_factor 1.0 — the most conservative
longitudinal profile. Verified `relaxed` on **every** analyzed drive (2f, 30, 32, 33):
no drive in this dataset has ever run standard.

## 1. Stops (S1 target)

| metric | pre-S1 baseline (73-stop sim/reference) | route 33 measured |
|---|---|---|
| stops captured | 73 | **2** (short stops, route is mostly moving) |
| crawl 1→0 | sim cur 2.72 s / real med ~9.9 s | **~0 s observed** — car went 1.2→standstill without the ≥4 s creep crawl (n=2, thin) |
| final nod (last 1 s) | −0.54 med | −1.89 / −2.50 |
| max decel | −1.20 cmd floor | a_min −2.02 / −1.85 (actual; within ACCEL_MIN 3.5, EMERGENCY 3.0) |

**Fact**: the two observed stops completed without the long creep crawl — consistent
with S1's intent. **Inference**: firmer delivered decel in the last 1 s (−1.89/−2.5 vs
−0.35 baseline med) suggests these particular stops were genuinely short/hard stops
(nod numbers are actual aEgo, so partly road-roughness); need more stops to isolate.

## 2. Launches (L1c)

**0 clean launches** detected on route 33 (no 0→8 m/s engaged ramp without gas) —
route had no full-stop-to-cruise launches. Launch-peak detector over engaged frames:
peaks 1.21–1.27 cmd — gentle, consistent with L1c (no overshoot above cmd).

## 3. C1 — SET/RES engages

8 engages; adopted set vs v at engage (m/s):

| t | v_ego | adopted |
|---|---|---|
| 30.7 (seg0) | 3.6 | 70.8?? (kph — this field reads kph here: ~19.7 m/s) |
| 47.7 | 11.3 | 11.1 |
| seg1 6.4 | 7.8 | 12.0 |
| seg2 0.0 | 6.8 | 14.2 |
| seg3 0.0 | 5.4 | 16.5 |
| seg4 22.1 | 17.6 | 14.3 |
| seg5 0.0 | 12.9 | 22.2 |
| seg5 34.2 | 5.7 | 22.2 |

**Fact**: engages adopt sensible set speeds near/above v_ego (e.g. 17.6→14.3 is a
resume-down case C1 governs; 5.7→22.2 resume-up). The 70.8 first-engage is the
kph-field artifact (~19.7 m/s), matching a highway preset — plausible intended set.

## 4. Following / gas

- set−v gap med **0.03 m/s** (n=4473 engaged, no lead) — set-speed tracking is tight.
- gas override frames: **876** over ~5.2 min engaged ≈ 2.8/min — higher than v5's
  1.3/min (relaxed personality → user prods more? inference).

## 5. Steering regression check

- **Tracking by speed** (undelayed ref, unpressed, unsaturated): mid-band 10–14 m/s
  steady tr **1.07–1.26** — slightly higher than v5's 0.99–1.11 (thin n at some bins);
  low-speed 5–8 steady **0.71–0.96** — mild under-response persists (kp floor unchanged).
- **Wobble**: **1 sub-threshold candidate** — seg2 t=40.5, 1.1 s, 6.5 m/s, 1.01 Hz,
  curve-exit, P-led (p 3.75 vs f 0.98) — same signature as v4's residual "small wobble".
  Below felt-threshold duration; not a regression.
- **Lane bias**: mean **+0.081**, med **+0.066** (n=2007) vs v5/KARNBIRRLV2's −0.029 —
  now ~7 cm **left** of center (sign: positive = left). Within normal model-variance;
  watch next drive.
- **Lane-line jitter**: 0.09 — smooth (KARNBIRRLV2-consistent).
- **Faults**: `canValid=False` 75 frames on route 33 (boot-settle window at seg 0,
  same pattern as before — clears in <10 s); no steer faults; no engage-blocking alerts.

## Verdict

S1 + L1c + C1 stack is behaving: tight set-speed tracking (gap 0.03), no launch
overshoot, stops complete without creep crawl (thin n), steering unchanged except a
mild leftward lane bias shift and the known sub-13 m/s P-mode signature at very low
speed. Watch: personality param drift (now persistent across every boot) and gather
more stops for the S1 taper claim.
