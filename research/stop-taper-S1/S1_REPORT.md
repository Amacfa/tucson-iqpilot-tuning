# S1 stop-taper package — build report (NOT installed)

## Delta
`iqpilot/selfdrive/controls/lib/smooth_stops.py`: `SETTLE_DECEL 0.80→1.00`,
`TAPER_SPEED 1.0→0.6` — exactly 2 changed lines, everything else byte-identical
(asserted by test_s1.py).

- Candidate sha256 `9da88dc07b34…`; rollback `b0ba5983fc0b…` (= current device file, verified on-device).
- Install stack expectation: v5 (`db166b61`) + D1 (`bbfa1b6e`) + L1c (`d3915221`) + C1 (`1abb8a1e`) — all pinned in validation_dependencies.

## Sim (settle() replay, 73 measured stops incl. v5 routes)

| metric | current | S1 |
|---|---|---|
| crawl 1→0 med | 2.72 s | 2.42 s |
| crawl p90 | 4.1 s | 2.9 s |
| final nod med/p10 | −0.54 / −0.66 | −0.54 / −0.66 |
| cmd floor | −0.80 | −1.00 |
| worst cmd | −1.20 | −1.20 |

No stop exceeds comfort decel; worst-case identical (−1.20 < EMERGENCY 3.0, ACCEL_MIN 3.5).
Lead-gap gating unchanged → stopping distance behind a lead cannot shorten.
Sim under-predicts absolute crawl (real median 9.9 s; creep-torque dynamics simplified) —
deltas and bounds are the reliable outputs.

## Tests
`test_s1.py` {"s1_ok": true, "changed_lines": 2}; `test_artifacts.py` hashes + patch roundtrip + py_compile ✓; `test_manage.py` all 7 guards ✓.
