# C1 — INSTALLED 2026-09-30

- Applied via `manage.py --apply` on comma, IsOffroad=1, HEAD 3736edc…
- Same `controlsd.py` dep-hash fix as L1c (pre-D1 `1cdb4917` → D1 `bbfa1b6e`; no
  interaction with the cruise.py set-speed changes).
- Installed file: `cruise.py` sha256 `1abb8a1e00c3…` (candidate ✓, verified post-reboot).
  Backup: `/data/iq-warning-backups/20260930T204309.632276Z-apply`.
- Rollback: `/data/tucson-packages/C1/package/manage.py --rollback` → restores stock `5dea5d19`.
- Hourly `installed_state` reports `C1:candidate_present`.
- Active model at install: KARNBIRRLV2 (index 77); `py_compile` clean; no boot faults.
