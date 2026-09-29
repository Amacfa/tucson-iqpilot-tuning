# tune-v3 — latAccelFactor speed-table refit (release 3736edc, layered over tune-v2)

Single-file delta to `iqpilot/selfdrive/controls/lib/latcontrol_torque.py`:
`LAT_ACCEL_FACTOR_SPEED_TABLE["HYUNDAI_TUCSON_4TH_GEN"]` changes
`([8,15,25],[2.95,3.35,3.70])` → `([8,12,15,25],[2.95,3.20,3.80,3.90])`.

Derivation: measured steady-state tracking ratio (actual/desired lat accel) per speed bin on the
3736edc+tune-v2 drives (v3b export, fit_lat_gain.py / LAT_GAIN_FIT.md): 1.04 @8–12, 1.19 @12–15,
1.08 @15–20, 1.075 @20–25 → table scaled by the per-bin ratio (FF over-torque correction);
low speed kept at 2.95 (0b8c/v2 ratios ≈1.0). Rollback restores the installed tune-v2 file
(sha256 b844c7ed…). Requires tune-v2 installed. Everything else in tune-v2 is unchanged
(friction 0.12, reduced-feedback path, no measurement filter).

NOT installed. Usage identical to sibling packages:
`manage.py --check | --apply | --rollback | --verify-installed` (run parked only).
See research/tune-v3-table/ for evidence and predicted effect.
