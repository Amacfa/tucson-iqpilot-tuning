# A3 installed — 2026-10-01

Package: `analysis/tucson-tune-3736edc-A3/package/` (cloned S1 format; all guard tests pass).

## Change
`iqpilot/selfdrive/controls/lib/longitudinal_planner.py` — one line:
`A_CRUISE_MAX_VALS = [2.0, 1.6, 0.8, 0.6]` → `[2.0, 1.6, 1.0, 0.6]`
(interp ceiling at the 25 m/s breakpoint 0.8→1.0; breakpoints, J_CRUISE, A_CRUISE_MIN,
accel limits, lead-mpc untouched; ≤ ACCEL_MAX 2.0; Hyundai/panda limits untouched).

## Install record
- `manage.py --check` → check_passed on first run (deps pinned to installed hashes:
  controlsd D1 `bbfa1b6e`, carcontroller L1c `d3915221`, cruise C1 `1abb8a1e`,
  latcontrol v5 `db166b61`, smooth_stops S1 `9da88dc0`)
- `--apply` → backup `/data/iq-warning-backups/20261001T061806.072817Z-apply`
- Reboot ~75 s; post-verify: `longitudinal_planner.py` `d6abce2e` ✓; S1 `9da88dc0`,
  L1c `d3915221`, C1 `1abb8a1e`, v5 `db166b61`, D1 `bbfa1b6e`, LFA-AB `cfd69418`,
  arming `a66a2baf` all unchanged; `py_compile` clean
- Params: `LongitudinalPersonality` 2 (relaxed — user's intended value, correctly
  persisted this time), `ExperimentalMode` False, `DisableUpdates` 1
- `active_model` 77/KARNBIRRLV2; `IsOffroad` True; hourly run.sh `warnings: []`

## Rollback (parked only)
`cd /data/tucson-packages/A3/package && /data/openpilot/.venv/bin/python manage.py --rollback`
→ restores `eaa3b4e1` (stock constants).
