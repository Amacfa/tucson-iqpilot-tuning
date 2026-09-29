# Offline validation results

Source data: /home/ubuntu/tucson/drives/all_frames.npy (731951 active frames with v >= 5 m/s). Low-pass alpha = 0.1429 (dt 0.01 s, tau 0.06 s).

## Steering torque: candidate vs baseline (open-loop arithmetic)

Baseline = logged |out|; recon = |(p+i+f)/2.960174| (checks the arithmetic); lp_only = P recomputed as kp*(dla - LP(ala)); schedule_only = baseline terms / interp(v,[8,15,25],[2.95,3.35,3.70]); candidate = both. Median logged p / (kp*err) = 1.0 (1.0 = reconstruction exact).

| speed bin (m/s) | frames | mean |tq| base | recon/base | lp_only/base | schedule_only/base | candidate/base |
|---|---|---|---|---|---|---|
| 5-10 | 209667 | 0.2522 | 1.2522 | 1.2389 | 1.2501 | 1.2367 |
| 10-15 | 261672 | 0.1041 | 1.0254 | 1.0391 | 0.9495 | 0.962 |
| 15-20 | 217759 | 0.0886 | 1.0019 | 1.0266 | 0.867 | 0.8884 |
| 20-25 | 24232 | 0.0631 | 1.0 | 1.0203 | 0.8282 | 0.8447 |
| 25-+ | 18621 | 0.0784 | 1.0 | 1.0158 | 0.8 | 0.8127 |

## Dither: RMS of frame-to-frame torque change x270 (contiguous active runs)

- baseline_recon: 9.727
- lp_only: 8.8579
- schedule_only: 9.6853
- candidate: 8.8323

By speed bin:
- baseline_recon: 5-10 7.859, 10-15 3.55, 15-20 3.17, 20-25 3.369, 25-+ 3.014
- lp_only: 5-10 7.024, 10-15 3.015, 15-20 2.576, 20-25 2.619, 25-+ 2.369
- candidate: 5-10 7.026, 10-15 2.796, 15-20 2.225, 20-25 2.172, 25-+ 1.895

## L1 jerk_u unit test

- jerk=0.0, accel=0.5 -> jerk_u=1.0
- jerk=0.0, accel=2.0 -> jerk_u=3.0
- jerk=1.5, accel=0.0 -> jerk_u=3.0
- jerk=0.0, accel=2.5 -> jerk_u=4.0
- jerk_l unchanged vs baseline formula over 6161 grid points: PASS


## v2 note

v2 candidate = schedule_only column (LP removed). Candidate/base mean |tq|:
5-10 1.2501, 10-15 0.9495, 15-20 0.867, 20-25 0.8282, 25+ 0.800.
Dither x270: 9.6853 overall (baseline 9.727, v1 8.83); by bin same as baseline
modulo the factor rescale.
