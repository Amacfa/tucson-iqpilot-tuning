# tune-v5 validation results (offline)

- `test_artifacts.py`: `{"all_three_file_hashes": true, "forward_reverse_patch_roundtrip": true, "candidate_and_rollback_py_compile": true}`
- `test_manage.py`: all 7 transaction guards true
- `validation/test_v5.py`: `{"v5_ok": true, "changed_lines": 2}` — table exact, monotonic, interp spot-checks pass; kp_scale/H1 LP preserved; diff = single table line
- candidate sha256 `db166b61…`; pre-state = v4 `9979c41b…` (installed)

## Open-loop replay prediction (v4 drive frames, mechanism_v3h1d1 replay harness)

Mid-band steady tracking (|ref| 0.5–1.5, naive tr*K_v4/K_v5 scale; closed-loop P/I
absorption means on-road residual will be nonzero):

| bin | measured tr | predicted v5 tr |
| 10 | 1.158 | 1.102 |
| 12 | 1.176 | 1.093 |
| 13 | 1.188 | 1.109 |
| 14 | 1.137 | 1.065 |
| 15 | 1.186 | 1.114 |

Exit-window |tq delta v5−v4|: mean 0.0038, max 0.0135 (n=18) — higher K shrinks the
torque for the same lat-accel command; negligible.

## Sims (route-26-seg-6 handback + v2_frames curve-exit, kp_low 0.7)

| case | ala_pp | band_1_3 | track_rms |
| v4 table | 0.507 | 0.629 | 0.098 |
| v5 table | 0.488 | 0.600 | 0.093 |

| curve-exit | band_tq | band_ala | rmse | dither |
| v4 | 0.533 | 0.238 | 0.263 | 0.80 |
| v5 | 0.534 | 0.239 | 0.260 | 0.80 |

Neutral-to-marginally-better. No regression.
