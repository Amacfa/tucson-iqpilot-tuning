# S1 drive-2 report — routes 33+34+35 pooled (S1+L1c+C1+v5, Relaxed, KARNBIRRLV2)

Ingest: `run.sh` pulled routes **00000034 (16 segs) + 00000035 (15 segs) = 31 segs**,
commit `ba4d892`, `warnings: []`, active model 77/KARNBIRRLV2, all packages
`candidate_present`. Pooled with route 33 → **37 segments**, ~99k engaged frames.
User feel report: "smooth". `selfdriveState.personality=relaxed` on all frames
(T_FOLLOW 1.75 s) — confirmed-intended value per the enum erratum.

## Stops (vs 73-stop pre-S1 baseline)

| metric | pre-S1 baseline | S1 pooled (n=8, all behind lead) |
|---|---|---|
| crawl 1→0 med / p90 | real ~9.9 s / — | **8.86 s / 19.2 s** |
| crawl ≥4 s share | ~86% | 4/8 (50%) |
| final nod med / p10 | −0.54 / −0.66 | **−0.33 / −0.56** (softer) |
| worst aEgo / cmd | ~−1.2 cmd floor | −1.44 / **−2.01** |

Measured: final nod improved (−0.33 vs −0.54); worst commanded decel −2.01 (still
<EMERGENCY 3.0, <ACCEL_MIN 3.5). Inference: half the "long crawls" (14–25 s) are
stop-and-go creep **following a lead** — creep is lead-gap-controlled, not the S1
taper window; n=8 is thin. No evidence of harshness; nod metric improved.

## Launches (L1c)

3 clean launches: cmd peaks **1.75 / 2.00 / 1.84** (≤ ACCEL_MAX 2.0, L1c-shape);
actual aEgo peaks 2.39 / 3.45 / 2.00. Inference: the 3.45 spike is a standstill-release
aEgo artifact (jerk 56 = frame-noise), same class as earlier drives — cmd side stayed
capped, which is what L1c controls. User reports smooth.

## C1 engages — 25

Adopted set ≈ current speed or prior-set resume (e.g. 13.6→14.7, 5.6→15.6, 22.8→20.0,
2.2→20.0 resume-up). Three seg-0 engages show a transient `set=70.8` HUD artifact
(persisted kph preset from prior drive) that resolves to ~11 within 3 s — cosmetic
residual, consistent with C1 then adopting current speed.

## Set-speed / cruise

- med |set−v| **0.019 m/s** (n=24.9k); p90 6.9 m/s is transient climb windows, not
  stuck-cap — every climb resolved (med climb 3.9 s). vs the 0.33 capped-share e2e
  era: **cruise-reaches-set stays fixed**.
- **Highway catch-up (#3 evidence)**: in the 15–25 m/s band, commanded |a| sat at the
  A_CRUISE_MAX 0.8 ceiling for **9.6% of frames**; 15 climb windows, med duration 3.9 s,
  med per-climb saturation 41%; three merges hit cmd 2.0–2.3 (accel-phase transients).
  **Verdict: moderate evidence** for #3 (A_CRUISE_MAX 0.8→1.0 @15–25) — ceiling contact
  is real but climbs already resolve quickly. Optional, low-risk.
- **#4 jerk_l_base**: weak evidence — nod improved to −0.33; nothing felt.
  Deprioritize.
- **#5 J_CRUISE**: no evidence — no user complaint, climbs fine. Leave.

## Following / lead

- T-gap med **2.35 s** vs relaxed T_FOLLOW 1.75 (gap_err med +8.8 m at speed): car
  keeps ~0.6 s more than the 1.75 target. Inference: relaxed profile is generous by
  design (matches user's comfort preference); correlates with gas-override context.
- Lead-decel reaction lag: **med 0.0 s, p90 0.31 s** (n=58) — excellent.

## Gas overrides

**3817 frames / 3.85%** of engaged: lead 1906, no-lead≥8 m/s 1232, launch 727,
cruise 647. Half of overrides happen behind leads — consistent with the generous
relaxed gap; user prods to close it.

## Steering regression

- Tracking |ala|/|dla| by speed: 10–16 m/s **1.05–1.13** (vs v5 0.99–1.11 — same range);
  20–21 m/s 1.20–1.23 (thin bins, lane-change bleed likely).
- Wobble: **2 sub-threshold candidates**, both ~6.3–6.5 m/s, 1.0 s, 1.01 Hz — the same
  known low-speed P-mode family; below felt level.
- **Lane bias (34/35, n=11633): +0.111 mean / +0.130 med** — the leftward lean under
  KARNBIRRLV2 persists and grew slightly vs route 33's +0.08; jitter 0.063 (smoother).
  Watch item; consider re-checking CameraOffset if it climbs past ~0.15.
- Faults: canInvalid 23/19 frames (seg-0 boot settle only); steerFault 0; commIssue/
  paramsdTemporaryError/posenetInvalid confined to boot windows. **1 `accFaulted`
  event** (route 35 seg 14, t+26.3 s) — single occurrence, recovered; new flag to watch.

## Verdict

Stack is healthy and "smooth" is corroborated: soft nods, capped launch commands,
tight set tracking, fast lead reaction. Watch list: leftward lane bias trend,
the single accFaulted, low-speed P-mode wobble residue. Remaining candidates:
#3 optional (moderate evidence), #4/#5 leave.
