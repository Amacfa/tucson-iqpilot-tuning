# A3 report — A_CRUISE_MAX_VALS 0.8→1.0 @25 m/s breakpoint

## Motivation (drive-s1b measured evidence)
On routes 33+34+35 (37 segs): commanded |a| sat at the 0.8 ceiling for **9.6%** of
15–25 m/s engaged frames; 15 climb windows, med saturation 41% per climb.

## Offline estimate (measured-episode replay, honest bound)
For each of 12 measured climb episodes (set−v>2, engaged+long, no gas), saturated
seconds at |acco|≥0.79 shrink 20% under a 1.0 ceiling:

| | med | total |
|---|---|---|
| climb duration measured | 7.8 s | 12 episodes, 19.0 s saturated |
| est. duration @1.0 | **7.3 s** | ~4 s saved across episodes |

Effect is modest but real on long climbs (a 10.3 s climb → ~9.5 s; 19.3 → ~18.7).

## Safety invariants
- `get_max_accel` only caps the **cruise** candidate (`clip(v_cruise−v_ego, A_CRUISE_MIN, max_accel)`);
  lead-mpc candidate and `min()` over candidates unchanged → **no interaction with following**.
- J_CRUISE / jerk shaping untouched → command ramp rate unchanged; only the ceiling raised.
- Max value 1.0 ≤ ACCEL_MAX 2.0; SCC jerk/panda limits untouched.

## Post-install verification
See INSTALLED.md — `d6abce2e` live, hourly `A3:candidate_present`, warnings: [].
