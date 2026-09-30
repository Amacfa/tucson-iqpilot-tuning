# S1 — INSTALLED 2026-09-30

- Applied via `manage.py --check` (passed first try — deps pinned to installed hashes:
  controlsd=D1 bbfa1b6e, carcontroller=L1c d3915221, cruise=C1 1abb8a1e,
  latcontrol=v5 db166b61) then `--apply`, parked, HEAD 3736edc…
- Installed file: `smooth_stops.py` sha256 `9da88dc07b34…` (candidate ✓, verified post-reboot).
  Backup: `/data/iq-warning-backups/20260930T221332.449098Z-apply`.
- Rollback: `/data/tucson-packages/S1/package/manage.py --rollback` → restores `b0ba5983` (parked only).
- Boot: `IsOffroad=1`, `DisableUpdates=1`, active model 77/KARNBIRRLV2, py_compile clean.
- `LongitudinalPersonality` reverted to 2 at this reboot (third occurrence — confirmed
  boot-revert); re-applied to 1. User should set Standard in the comma UI to persist it.
- Hourly `installed_state` reports `S1:candidate_present`.
