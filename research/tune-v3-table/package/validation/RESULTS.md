# tune-v3 (LAT_ACCEL_FACTOR_SPEED_TABLE refit) validation

- test_table.py: `{"table_refit_ok": true}` — candidate table == ([8,12,15,25],[2.95,3.20,3.80,3.90]),
  monotone, interp spot-checks (10→3.075, 13.5→3.5, 20→3.85), candidate identical to rollback
  outside the table literal.
- test_artifacts.py: all_three_file_hashes, forward/reverse patch roundtrip (byte-identical),
  candidate+rollback py_compile — all true.
- test_manage.py: all 7 transaction guards pass (apply/rollback exact, partial-write restore,
  temp cleanup, unrelated-edit refusal, mixed-state rollback, receipt-failure restore, -O guards).
- Device pre-state verified read-only 2026-09-29: iqpilot/selfdrive/controls/lib/latcontrol_torque.py
  sha256 b844c7ed… == tune-v2 candidate == manifest original_sha256. NOT applied; offline only.
