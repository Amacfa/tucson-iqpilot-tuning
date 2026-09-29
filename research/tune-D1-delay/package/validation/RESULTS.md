# D1 validation
- test_d1.py: `{"d1_ok": true, "added_lines": 6}` — fingerprint+unestimated gate present;
  simulated clamp: 0.30→0.15 unestimated; estimated/invalid pass through; lower real value kept;
  other fingerprints untouched; diff is purely additive (6 added lines, no removals).
- test_artifacts.py: hash + forward/reverse roundtrip + py_compile — all true.
- test_manage.py: 7 transaction guards pass.
- Device pre-state verified read-only: controlsd.py sha256 1cdb4917… matches manifest.
