# latAccelFactor + friction fit vs speed (v3b)

Model: `tqo = ala / K_eff + friction_eff·sign(ala)` (Huber on [ala, sign(ala)]).
Steady-state: lat active & engaged, prs==0, |rate|<15 deg/s, 0.15≤|ala|≤2.5, |tqo|<0.9, v≥5, 1.5 s cooldown after steerPressed/blinker.
Current table: [8,15,25] → [2.95,3.35,3.70]. tracking = median(ala·sign(dla))/median|dla| on |dla|>0.3.
K_yaw refits torque vs yawRate·vEgo (independent measure).

## 0b8c190c_pre_tune

| bin | n | K_eff (ala) | 95% CI | friction_eff | 95% CI | table@center | table/K | tracking | K_eff (yaw) | friction (yaw) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5–8 | 1568 | 2.05 | 1.99-2.11 | -0.049 | -0.057--0.042 | 2.95 | 1.44 | 0.990 | - | - |
| 8–12 | 2347 | 5.40 | 4.88-6.12 | -0.024 | -0.033--0.016 | 3.06 | 0.57 | 1.047 | - | - |
| 12–15 | 4497 | 11.99 | 11.22-12.79 | 0.032 | 0.028-0.036 | 3.26 | 0.27 | 1.101 | - | - |
| 15–20 | 10751 | 8.88 | 8.57-9.17 | -0.010 | -0.013--0.007 | 3.44 | 0.39 | 1.179 | - | - |

## baseline_pre0b8c190c

| bin | n | K_eff (ala) | 95% CI | friction_eff | 95% CI | table@center | table/K | tracking | K_eff (yaw) | friction (yaw) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5–8 | 4176 | 4.10 | 3.87-4.33 | -0.062 | -0.067--0.057 | 2.95 | 0.72 | 0.855 | - | - |
| 8–12 | 12131 | 9.04 | 8.46-9.69 | -0.002 | -0.005-0.001 | 3.06 | 0.34 | 1.003 | - | - |
| 12–15 | 17284 | 10.77 | 10.31-11.21 | 0.012 | 0.010-0.014 | 3.26 | 0.30 | 1.168 | - | - |
| 15–20 | 33411 | 12.06 | 11.77-12.35 | 0.008 | 0.007-0.010 | 3.44 | 0.28 | 1.178 | - | - |
| 20–25 | 3685 | 21.91 | 20.48-23.52 | 0.018 | 0.017-0.020 | 3.61 | 0.16 | 1.113 | - | - |
| 25–40 | 1642 | 26.86 | 25.14-28.89 | 0.017 | 0.014-0.020 | 3.70 | 0.14 | 1.332 | - | - |

## v1_route24

| bin | n | K_eff (ala) | 95% CI | friction_eff | 95% CI | table@center | table/K | tracking | K_eff (yaw) | friction (yaw) |
|---|---|---|---|---|---|---|---|---|---|---|
| 8–12 | 470 | 11.03 | 9.30-13.73 | -0.007 | -0.022-0.010 | 3.06 | 0.28 | 1.196 | - | - |

## v2

| bin | n | K_eff (ala) | 95% CI | friction_eff | 95% CI | table@center | table/K | tracking | K_eff (yaw) | friction (yaw) |
|---|---|---|---|---|---|---|---|---|---|---|
| 5–8 | 647 | 2.96 | 2.73-3.31 | -0.039 | -0.050--0.026 | 2.95 | 1.00 | nan | - | - |
| 8–12 | 3536 | 4.55 | 4.16-5.05 | -0.015 | -0.022--0.009 | 3.06 | 0.67 | 1.039 | - | - |
| 12–15 | 7036 | 7.19 | 6.96-7.53 | 0.002 | -0.001-0.005 | 3.26 | 0.45 | 1.193 | - | - |
| 15–20 | 12266 | 7.23 | 6.92-7.53 | -0.011 | -0.014--0.009 | 3.44 | 0.48 | 1.084 | - | - |
| 20–25 | 5031 | 15.65 | 14.18-17.46 | 0.013 | 0.009-0.017 | 3.61 | 0.23 | 1.075 | - | - |

## Caveats

- `carState.yawRate` (`yaw`) is **all zeros** in the v3b export — the yaw×v cross-fit could not be computed; K_yaw/f_yaw columns are empty.
- EPS torque sign is opposite to latAccel sign; fits were done on `-tqo` (latAccel sign convention).
- K_eff exceeds the a-priori plausibility bound (1.5–5) at most bins — the relationship is **nonlinear**: per-|ala| band medians (v2, steady state) show the effective gain is much higher at low accel and compresses toward ~4–8 at |ala|>0.8:

  | v bin | |ala| band | n | median |tq| | median |ala| | implied K |
  |---|---|---|---|---|---|
  | 8–12 | 0.15–0.4 | 3624 | 0.057 | 0.246 | ~4.3 |
  | 8–12 | 0.8–1.4 | 195 | 0.366 | 1.056 | ~2.9 |
  | 12–15 | 0.4–0.8 | 2653 | 0.104 | 0.591 | ~5.7 |
  | 12–15 | 1.4–2.5 | 475 | 0.239 | 1.725 | ~7.2 |
  | 15–20 | 0.8–1.4 | 1350 | 0.119 | 1.015 | ~8.5 |
  | 15–20 | 1.4–2.5 | 187 | 0.210 | 1.543 | ~7.3 |
  | 20–25 | 0.15–0.8 | 849 | ~0.04 | ~0.35 | ~8.3 |

  Reading: the friction offset (~±0.05 torque near zero accel) plus feedback dynamics inflate the low-accel intercept; the large-accel points are the more meaningful gain. Either way, the measured effective gain at 12–25 m/s is materially **higher** than the table (3.26–3.61): the table under-estimates latAccelFactor, so the FF path commands ~2–4× too much torque — consistent with tracking >1 in the same bins. The learner being invalid means these table values were the whole correction.
- Sanity: all v2 bins with data have n ≥ 647 (four bins > 3500); CIs are tight.
