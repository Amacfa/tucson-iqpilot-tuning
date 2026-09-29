# First drive: tune-v3 + H1 + D1 — route 0000002d (2026-09-29)

Installed before drive (~20:37 UTC, reboot verified): `latcontrol_torque.py = 97cc8ee4` (H1 over tune-v3 `277aff99`), `controlsd.py = bbfa1b6e` (D1 over stock). Drive = route `0000002d--7116f1d7a1--0..9` (10 segs, ~343 s engaged, lon 309 s). Group label `v3h1d1` added to closeout_v3b.py.

**Pipeline note**: the staged device exporter writes to `/data/tucson-drive-export-v3` (pre-rename copy), while refresh.py pulled `…-v3b`; all 10 segments exported fine into the v3 dir and were pulled manually. refresh.py `DEVICE_OUT` corrected to match.

User feel: "mostly alright; one wobble that self-corrected in 2–3 s; in turns a bit aggressive / over-correcting", plus "even non-overturning curves felt uncomfortable".

## Wobble episode analysis (all-speed scan, closeout detector extended)

Three episodes detected; the felt one is almost certainly **seg 5, t≈51 s, v=10.8 m/s** (3.0 s, self-corrected):

| seg@t | v | dur | ctx | dom freq | amp(-tqo hi-pass) | f_rms | p_rms | out_rms | corr(f,p) |
|---|---|---|---|---|---|---|---|---|---|
| 2d--1 @40.5 | 7.4 | 3.2 s | post-override | 0.67 Hz | 0.17 | 1.60 | 2.64 | 0.70 | −0.07 |
| 2d--3 @39.0 | 13.8 | 3.0 s | curve-exit | 1.34 Hz | 0.16 | 0.31 | 0.59 | 0.20 | +0.20 |
| 2d--5 @51.0 | 10.8 | 3.0 s | straight (dla_max 3.0 — just after strong demand) | **1.67 Hz** | 0.22 | 1.08 | 1.29 | 0.41 | −0.25 |

- Felt episode (seg5) is a **P-dominated ~1.7 Hz** burst — same frequency as the v2 episodes (dom 1.7 Hz, friction_episodes.json), but now p and f are **weakly anti-phase** (corr −0.25 vs v2's +0.70 in-phase) and it self-terminated in 3 s. Consistent with H1's kp scale-down ramping in around 13–17 m/s — at 10.8 m/s the P cut hasn't engaged yet, so the residual 1.7 Hz mode persists at low speed.
- The seg1 post-override episode is low-speed (7.4 m/s), post-hander err settling — P-term RMS 2.64 is the biggest term there.
- Episode rate: v3h1d1 10–15 m/s = **218/10min** on 0.046 h (1 ep) — small-n; v2 had 0 at 10–15 and 138 at 15–20. Curve-exit wobble band_rms 6.72 vs v2 5.98 / baseline 6.69 — **not better yet** (n=13, small drive).

## In-turn behaviour ("aggressive / over-correcting")

Curve detector: |dla|>0.8 for ≥2 s, lat engaged, no override. v3h1d1 n=3, v2 n=17, baseline n=76, human n=75 (lat-off curves, |v²·ang/L|>0.8).

| group | tr entry | tr mid | tr exit | overshoot@entry | tq_rate rms | p_rms | jerk rms | jerk pk | sign rev/curve | ang_rate rms |
|---|---|---|---|---|---|---|---|---|---|---|
| v3h1d1 | 1.05 | 1.08 | **1.44** | 0.98 | 0.68 | 0.63 | 1.35 | **12.4** | 0.7 | **31.3** |
| v2 | 1.08 | 1.07 | 1.08 | 1.11 | 0.90 | 0.51 | 1.27 | 7.2 | 1.1 | 34.4 |
| baseline | 1.12 | 1.11 | 1.15 | 1.13 | 0.77 | 0.59 | 1.19 | 6.2 | 2.9 | 24.5 |
| human (ref) | — | — | — | — | — | — | 14.6* | 103.7* | — | **16.6** |

\* human jerk is from the ang-proxy (v²·ang/L), which amplifies angle-sensor noise — the ratio is not meaningful; the meaningful human comparison is `ang_rate_rms`.

**Findings:**
- **No FF overshoot at entry** (0.98 < v2's 1.11) — the v3 table refit did its job at entry/mid (tr 1.05/1.08).
- **"Over-correcting" lives at curve EXIT**: tracking ratio 1.44 at exit vs ~1.08 for v2/baseline. The car keeps making lateral accel while the path asks it to unwind — likely the dominant "aggressive" feel. n=3, but consistent with saturation below.
- **Comfort**: lateral jerk rms 1.35 ≈ v2 (1.27) but **peak jerk 12.4 vs 7.2** — sharper spikes; steering-angle rate RMS 31.3 deg/s vs human 16.6 (ratio **1.9×**) and vs baseline 24.5. Torque-rate RMS is actually *lower* than v2 (0.68 vs 0.90) and P-term RMS similar — so it's **not a "P too sharp" story in average terms**; the discomfort is in the peaks/exits.
- **Phase at curve entry**: desired→actual xcorr lag ≈ **0.00 s median** (n=2; a second run with the older binning gave 0.33 s on the same pair — unstable on tiny n). With D1 active the lookahead is 0.15 s; lag ≈0–0.3 means **no evidence of excessive lookahead** (which would show actual *leading* desired, negative lag). The aggressive feel is therefore amplitude/exit-tracking, not phase-lead.
- D1 clamp confirmed active: `LiveDelay` param still `lateralDelay=0.30, status=unestimated, calPerc=0` post-drive → consumer clamp min(0.30,0.15)=0.15 s applies. lagd still has not learned.

## Tracking ratio per speed bin (steady |dla| 0.3–0.7, 0.3 s lag)

| bin | v3h1d1 | v2 | baseline | v3 prediction |
|---|---|---|---|---|
| 5–10 | 0.82 | 0.87 | 0.90 | — |
| 10–15 | 1.11 | 1.12 | 1.09 | ~1.03 |
| 15–20 | 0.86 (n=266) | 1.06 | 1.08 | ~0.98 |

Small n on the new group (626/721/266 frames); 15–20 reading may be dominated by a couple of exits. **Not yet confirming the 0.98–1.03 prediction — needs more drive data.**

## Faults / saturation / overrides / alerts

- sft/sfp: **0 / 0**. steerPressed share 7.6–10.6% (v2: 11–17%). 
- **Saturation: 1.12% of active frames** — ~30× v2/baseline (0.038%). Worth watching; consistent with exit over-demand pushing |out| to clip.
- Alerts: only `Pay Attention`/`Driver Distracted` and `Steer Right / Confirm Lane Change` / `Changing Lanes` — **no LKA/LFA fault or steering-fault events**.

## Longitudinal (tune-v2 behaviour expected; L1c/C1 not installed)

Route 2d: lon_s 308.7, launches 1, engages 3, gas overrides 9.
- Launch T=299.5: ju_rel 2.6, a_peak1s 2.54, cmd_peak3s 2.0, sag_min 0.99 — same shape as v2 launches.
- Stale-set engage: **T=407.0, v=20.75 set=16.89 gap −3.86, min_acco_6s −1.68** — same class of stale set-speed braking as route 2c (the un-fixed C1 case). Other engages benign (gap −0.13, +5.11).

## Bottom line

v3+H1+D1 is safe to keep driving: no faults, wobble self-corrects faster and remains P-carried, entry/mid tracking corrected to ~1.05–1.08. Two open items for the next tune iteration: (1) **curve-exit over-tracking 1.44 + peak lateral jerk 12.4** — candidate directions: slew-limit the desired-lataccel unwind or damp exit-side P; (2) **residual 1.7 Hz P-mode at 10–12 m/s** (below H1's 13 m/s ramp) — consider extending kp scale-down or LP filtering lower. Saturation 1.12% needs watching on the next drive.

## Reproduction

`drive_v3h1d1.py` (episode + curve metrics), `drive_v3h1d1_detail.py` (episode detail incl. per-term breakdown, context, comfort + human reference), `closeout_v3b.py` (group tables), all reading `drives/export-v3b` one segment at a time.
