# v4 first drive — route 0000002e (2026-09-30)

Installed: `latcontrol_torque.py = 9979c41b` (v4 = H1 + kp_scale floor 0.7 below 13 m/s), `controlsd.py = bbfa1b6e` (D1). Post-drive `installed_state` verified: `tune-v4:candidate_present`, `D1:candidate_present`, `lfa-ab:candidate`, `DisableUpdates=1`. Route 0000002e = 33 segments, ~633 s longitudinal-active — a much bigger sample than route 2d (~343 s).

User feel: "felt pretty great, maybe a small wobble".

## Side-by-side closeout (same detectors as V3H1D1 report)

| metric | baseline | v2 | v3H1D1 | **v4** |
|---|---|---|---|---|
| curve-exit wobble band_rms | 6.69 | 5.98 | 6.72 | **3.35** |
| exit f_tq / sign_chg | 0.360/4.9 | 0.331/4.1 | 0.312/5.4 | **0.261/2.1** |
| osc episodes 10–15 m/s per10min | 21 | 0 | 218 (n=1) | **0** |
| osc episodes 15–20 per10min | 276 | 138 | 0 | **0** |
| lane-change handback median | 0.235 | 0.135 | 0.072 | 0.111 (n=7) |
| sat % active frames | 0.038 | 0.039 | **1.117** | **0.000** |
| steerPressed share | 11.7% | 11.1% | 7.6% | **5.5%** |
| sft/sfp faults | 1847/0 | 0/0 | 0/0 | **0/0** |

## Episodes

**Zero oscillation episodes detected** across all speed bins on route 2e (3 s windows, err band-frac>0.6, amp>0.4 — the detector that found the 10.8 m/s/1.67 Hz episode on v3H1D1). The user's "small wobble" did not trip the detector — either shorter than 3 s or smaller amplitude; no large-scale low-speed P-mode remains measurable. **The <13 m/s P-driven episodes are gone** (the v3H1D1 drive had 218/10min at 10–15 m/s and a P-dominated 1.67 Hz episode at 10.8 m/s).

## Curves — undelayed desired reference (mechanism-study convention)

Tracking uses dla back-shifted by the group's own lat_delay (0.15 s for v3h1d1/v4, 0.30 for v2/baseline) so all groups compare on the same physical demand — removing the lookahead-metric confound identified in the mechanism study.

| group | n | tr entry | tr mid | tr exit | tq_rate | p_rms | i_rms | jerk_rms | jerk_pk | steer-rate rms |
|---|---|---|---|---|---|---|---|---|---|---|
| v4 | 4 | 1.07 | 1.10 | **1.31** | 0.72 | 0.32 | 0.17 | 0.91 | **5.9** | **21.1** |
| v3h1d1 | 4 | 0.93 | 1.05 | 1.42 | 0.70 | 0.47 | 0.28 | 1.25 | 10.2 | 27.4 |
| v2 | 15 | 0.88 | 1.03 | 1.24 | 0.88 | 0.47 | 0.11 | 1.08 | 6.0 | 27.5 |
| baseline | 75 | 0.97 | 1.09 | 1.30 | 0.76 | 0.57 | 0.14 | 1.05 | 5.2 | 20.2 |
| human ref | 75 | — | — | — | — | — | — | 14.6* | 103.7* | 16.6 |

\* human jerk uses the noisy v²·ang/L proxy — only steer-rate is comparable.

- **Comfort improved on every metric**: peak lateral jerk 5.9 (v3h1d1 10.2), jerk_rms 0.91, steering-rate RMS 21.1 ≈ baseline 20.2 (down from 27.4; human 16.6 → ratio 1.27×, was 1.9× on v3h1d1). Matches "felt pretty great".
- Exit tracking 1.31 still >1 on the undelayed reference — residual physical unwind lag; note on the same undelayed reference v2 reads 1.24, so the v4 residual is ~0.07 above v2 (was 1.42 vs 1.24 on-delayed — the D1 timing explains most of the apparent v3h1d1 excess, as the mechanism study predicted).
- **Under-turn check**: tracking-by-speed 5–10 m/s = **0.94** (n=1513, borderline vs the 0.95 threshold), 10–15 = 1.15 (n=4309), 15–20 = 1.11 (n=2013). So at 5–10 the car under-tracks slightly — consistent with ×0.7 P: not alarming, watch next drive.
- **Integrator**: i_rms per curve 0.17 vs v2 0.11 — a modest increase compensating for lower P at 5–13 m/s, much less than v3h1d1's 0.28 (which was inflated by episode ringing). No runaway integrator signature.

## Saturation

**0.000%** of active frames saturated — the 1.12% rate on v3H1D1 is gone (that drive's sats were low-speed demand-at-slew-cap + P-led override settles; this route had fewer tight corners and none of the override settles that clipped).

## Longitudinal (tune-v2 stack expected; L1c/C1 still not installed)

Route 2e: lon 633 s, **3 launches** (a_peak1s 2.34/2.41/2.38, ju_rel 2.4–2.7, sag 1.16–1.33 — same v2-class shape), **6 engages**, **12 gas overrides**. No severe stale-set braking: engages with set>v are normal resume accelerations (gap +4.4/+10.4/+11.0); the only set<v cases are mild (gap −2.0, min_acco −0.14; and T=1865 gap +11.0 with min_acco −2.31 but driver on gas).

## Status / alerts / delay learner

- sft/sfp **0/0**; onroad alerts unchanged (Pay Attention / lane-change prompts only — no LKA/LFA fault).
- `LiveDelay` post-drive: **0.30 s, unestimated, calPerc 0** — lagd still has not produced an estimate, so D1's clamp continues to apply (0.15 s).
- `LiveTorqueParameters` unchanged from prior decode (invalid, table-driven).

## Bottom line

v4 delivered: zero detected oscillation episodes, lowest curve-exit band_rms of any group (3.35), zero saturation, lowest override share, and comfort metrics back to baseline/human-adjacent levels. Residual watch items: 5–10 m/s tracking 0.94 (mild under-turn from ×0.7 P — integrator is absorbing it) and exit-tracking ~1.3 residual unwind lag (≈v2-level once measured on the common reference; partially metric timing). If the "small wobble" recurs, catch it with a sub-3 s detector next pull; no new candidate warranted from this data alone.

Scripts: `drive_v4_detail.py` (episodes + undelayed-reference curves + comfort + i_rms), `closeout_v3b.py` (v4 group added), data in `drives/export-v3b/0000002e*`.

## Follow-up: sub-threshold wobble hunt + tracking detail (2026-09-30)

### Sub-threshold wobble hunt
Detector: joint sliding windows 1.0/2.0/3.0 s over the whole route; require band-frac>0.5 in the **1.0–2.5 Hz** band on `-tqo` with amp>0.2 (≈0.5× the v3h1d1 episode threshold), ala amp>0.15, ang amp>0.8; joint score ranked, overlapping windows deduped.

**One candidate survived** — the likely felt "small wobble":

| seg@t | dur | v | freq | p_rms | i_rms | f_rms | out_rms | ctx | lead |
|---|---|---|---|---|---|---|---|---|---|
| 2e--31 @47.1 | 1.1 s | 6.0 m/s | 1.01 Hz | 1.21 | 0.21 | 1.06 | 0.41 | curve-exit | P-led |

Self-terminating (1.1 s), low speed, **P-led** but shallow — same family as the v3h1d1 low-speed episodes at half the frequency and a third the duration. No candidates near a lane change or in the ≥13 m/s kp region.

### Tracking by speed, 1 m/s bins, undelayed ref, unpressed/unsaturated, |ref| split
(format: `tr`, signed-mean p and i — sign = relative to desired direction; negative p = feedback pulling AGAINST desired = over-production)

- **v4 10–16 m/s, mid-band steady**: tr **1.14–1.18** with signed p ≈ **−0.15…−0.28**, i ≈ 0.03–0.12 → the car over-produces lateral accel through feedforward and P/I trim it back → **FF over-scaled**, not a lane-model under-ask. Same signature in **v2** at the same bins (1.10–1.16, p −0.1…−0.3) → **inherited, not a v4 regression**; v3h1d1's exit bins showed extreme negative p (−1.8…−5.4) from the unwind fight, now gone.
- **v4 5–7 m/s steady hi-demand**: tr 0.85–1.09, mid-band entry at 6 m/s tr 0.71 → the ×0.7 P **is** producing a real (if mild) under-response at 5–7 m/s — matches the 5–10 bin 0.94 in the closeout. Signed p is positive (pulling with desired) there — the loop is doing its best within the scaled gain; i compensates partially (i_rms 0.17 vs v2 0.11).
- **Exits** (both groups): tr 1.2–1.7 at all speeds with negative signed p — physical unwind lag, P pulling against the still-high actual. Same shape in v2; not a regression.
- **16–19 m/s exits**: tr up to 1.45–1.69 on small n — same unwind mechanics at higher demand.

Net: the 10–20 m/s 1.11–1.15 over-track is **feedforward latAccelFactor still a touch low in that range** (v3 3.80 at 15 could go ~+5–10%); low-speed 5–7 m/s shows a small under-response from v4's ×0.7 P — if user feel reports under-steer at parking speeds, the next knob is interpolating 0.7→1.0 below ~7 m/s rather than raising the whole floor. No candidate built — data supports either staying on v4 or a micro-refit.

Script: `v4_followup.py`.
