# tune-v4 validation results (offline)

- `test_artifacts.py`: `{"all_three_file_hashes": true, "forward_reverse_patch_roundtrip": true, "candidate_and_rollback_py_compile": true}`
- `test_manage.py`: all 7 transaction guards true
- `validation/test_v4.py`: `{"v4_ok": true, "changed_lines": 4}` — kp_scale interp verified at 5/13/15/17/25 m/s → 0.7/0.7/0.65/0.6/0.6; H1 LP + kp_base preserved; diff vs H1 = exactly 4 +/- lines (comment + interp values)
- candidate sha256 `9979c41b…`; pre-state = H1 `97cc8ee4…` (verified installed on device, read-only)

## Sims (analysis/wobble, route-26-seg-6 handback + v2_frames curve-exit)

| case | ala_pp | band_1_3 | track_rms |
|---|---|---|---|
| v3 base | 1.033 | 0.929 | 0.297 |
| H1 ([1.0,0.6]+lp) | 0.507 | 0.629 | 0.098 |
| v4 ([0.7,0.6]+lp) | 0.507 | 0.629 | 0.098 |
| alt 0.6 flat | 0.507 | 0.629 | 0.098 |

| curve-exit (v3 table) | band_tq | band_ala | rmse | dither |
|---|---|---|---|---|
| kp_low 1.0 (H1) | 0.543 | 0.236 | 0.269 | 0.81 |
| kp_low 0.7 (v4) | 0.533 | 0.238 | 0.263 | 0.80 |
| kp_low 0.6 | 0.526 | 0.238 | 0.263 | 0.80 |

Handback excitation is ≥17 m/s so v4 ≡ H1 there (expected); curve-exit is marginally
better at 0.7. No regression.
