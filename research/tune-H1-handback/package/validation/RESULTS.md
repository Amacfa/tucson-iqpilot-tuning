# H1 validation
- test_h1.py: `{"h1_ok": true, "changed_lines": 9}` — P-scale interp(13/15/17→1.0/0.8/0.6),
  clamps at 5 and 20 m/s asserted; friction LP init/update/input lines present; only 9 diff lines.
- test_artifacts.py: hash + forward/reverse roundtrip + py_compile — all true.
- test_manage.py: 7 transaction guards pass.
- Sim (sim_friction.py, exact shaping): ala_pp 1.033→0.507, band 0.929→0.629.
