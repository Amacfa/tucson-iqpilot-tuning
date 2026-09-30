# L1c — INSTALLED 2026-09-30

- Applied via `manage.py --apply` on comma, IsOffroad=1, HEAD 3736edc…
- Manifest fix first: `controlsd.py` validation dep updated `1cdb4917` → `bbfa1b6e` (D1
  hash; D1 only changed the Tucson lateral-delay cap — no interaction with the
  carcontroller jerk-launch cap). CHECKSUMS.json regenerated.
- Installed file: `carcontroller.py` sha256 `d39152216200…` (candidate ✓, verified
  post-reboot). Backup: `/data/iq-warning-backups/20260930T204303.353231Z-apply`.
- Rollback: `/data/tucson-packages/L1c/package/manage.py --rollback` → restores tune-v2 `a8cf776c`.
- Hourly `installed_state` reports `L1c:candidate_present`.
