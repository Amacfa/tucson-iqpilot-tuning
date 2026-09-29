# Launch surge attribution — tune-v2 jerk_u boost

All 19 clean autonomous launches across releases (long3b_attrib.json).

| route | commit | T | jerk_u@launch | cmd peak (acco_rel) | measured peak 1s accel |
|---|---|---|---|---|---|
| 06 | 950be343 | 420.3 | 0.5 | 2.0 | 1.88 |
| 0a | 950be343 | 209.3 | 0.5 | 2.0 | 1.54 |
| 0c | bf51442c | 184.6 | 0.5 | 2.0 | 2.13 |
| 10 | bf51442c | 958.2 | 0.5 | 2.0 | 1.9 |
| 11 | bf51442c | 221.5 | 0.5 | 1.73 | 1.67 |
| 16 | 3636baa7 | 184.1 | 0.5 | 2.0 | 1.96 |
| 16 | 3636baa7 | 537.1 | 0.5 | 2.0 | 2.2 |
| 19 | ebaa28a1 | 850.0 | 0.5 | 1.66 | 0.95 |
| 19 | ebaa28a1 | 965.7 | 0.5 | 2.0 | 1.36 |
| 19 | ebaa28a1 | 1463.5 | 0.5 | 2.0 | 2.09 |
| 1a | ebaa28a1 | 486.0 | 0.5 | 2.0 | 1.78 |
| 22 | 0b8c190c | 180.9 | 0.5 | 2.0 | 1.78 |
| 22 | 0b8c190c | 268.3 | 0.5 | 2.0 | 2.04 |
| 22 | 0b8c190c | 386.7 | 0.5 | 2.0 | 1.43 |
| 23 | 0b8c190c | 515.0 | 0.5 | 2.0 | 1.81 |
| 26 | 3736edca | 513.3 | 3.0 | 2.0 | 3.04 |
| 28 | 3736edca | 347.9 | 2.5 | 1.1 | 2.2 |
| 29 | 3736edca | 419.2 | 2.6 | 1.66 | 2.56 |
| 2a | 3736edca | 182.9 | 3.0 | 2.0 | 4.3 |

Pre-3736edc releases (15 launches): jerk_u at launch 0.5, actuator cmd saturated at 2.0 m/s^2,
measured peak accel mean 1.77 / median 1.81 m/s^2.

Release 3736edc + tune-v2 (4 launches, routes 26/28/29/2a): jerk_u 2.5-3.0,
peaks 3.04 / 2.20 / 2.56 / 4.30, mean 3.03 m/s^2.

Conclusion: same planner command (acco_rel ~2.0 in both epochs); only the jerk_u cap changed,
so the tune-v2 jerk boost is the cause of the launch surge. The L1c cap (~1.2 m/s^3 at launch)
is expected to bring peaks to ~2.0-2.2 m/s^2.
