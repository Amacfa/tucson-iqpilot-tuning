# Offline validation results

Source data: /home/ubuntu/tucson/drives/all_frames.npy (717248 active frames with v >= 5 m/s). Low-pass alpha = 0.1429 (dt 0.01 s, tau 0.06 s).

## Steering torque: candidate vs baseline (open-loop arithmetic)

Baseline = logged |out|; recon = |(p+i+f)/2.960174| (checks the arithmetic); lp_only = P recomputed as kp*(dla - LP(ala)); schedule_only = baseline terms / interp(v,[8,15,25],[2.95,3.35,3.70]); candidate = both. Median logged p / (kp*err) = 1.0 (1.0 = reconstruction exact).

| speed bin (m/s) | frames | mean |tq| base | recon/base | lp_only/base | schedule_only/base | candidate/base |
|---|---|---|---|---|---|---|
| 5-10 | 202659 | 0.2542 | 1.2562 | 1.2425 | 1.2541 | 1.2403 |
| 10-15 | 254787 | 0.1046 | 1.0243 | 1.0383 | 0.9484 | 0.9611 |
| 15-20 | 216949 | 0.0888 | 1.0016 | 1.0264 | 0.8667 | 0.8882 |
| 20-25 | 24232 | 0.0631 | 1.0 | 1.0203 | 0.8282 | 0.8447 |
| 25-+ | 18621 | 0.0784 | 1.0 | 1.0158 | 0.8 | 0.8127 |

## Dither: RMS of frame-to-frame torque change x270 (contiguous active runs)

- baseline_recon: 9.7636
- lp_only: 8.8794
- schedule_only: 9.7218
- candidate: 8.8538

By speed bin:
- baseline_recon: 5-10 7.906, 10-15 3.553, 15-20 3.175, 20-25 3.369, 25-+ 3.014
- lp_only: 5-10 7.046, 10-15 3.003, 15-20 2.58, 20-25 2.619, 25-+ 2.369
- candidate: 5-10 7.048, 10-15 2.785, 15-20 2.228, 20-25 2.172, 25-+ 1.895

## L1 jerk_u unit test

- jerk=0.0, accel=0.5 -> jerk_u=1.0
- jerk=0.0, accel=2.0 -> jerk_u=3.0
- jerk=1.5, accel=0.0 -> jerk_u=3.0
- jerk=0.0, accel=2.5 -> jerk_u=4.0
- jerk_l unchanged vs baseline formula over 6161 grid points: PASS

