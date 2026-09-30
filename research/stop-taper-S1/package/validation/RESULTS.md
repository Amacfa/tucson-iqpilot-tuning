# S1 offline validation

## Sim: settle() replay over 73 measured stop approaches (all drives incl. v5/L1c routes)

Model: settle() under current vs S1 constants; delivered accel = commanded × measured
delivery fraction (interp 0.70/0.57/0.33/0.54/0.75 at v 0/0.25/0.5/1.0/1.5 from the
STOP_TAPER medians). Metrics below 1 m/s.

| metric | current (0.80/1.0) | S1 (1.00/0.6) |
|---|---|---|
| crawl time 1→0 med | 2.72 s | 2.42 s |
| crawl p90 | 4.1 s | 2.9 s |
| stall s med | 0.0 | 0.0 |
| final nod med (last 1 s) | −0.54 m/s² | −0.54 m/s² |
| final nod p10 | −0.66 | −0.66 |
| cmd floor med | −0.80 | −1.00 |
| cmd min (worst) | −1.20 | −1.20 |

(Measured real-world crawl 1.2→0.05 m/s is 9.9 s median — the sim under-predicts
absolute crawl because creep-torque dynamics aren't fully modeled; the *deltas* and
the unchanged safety bounds are the reliable outputs.)

## Safety bounds confirmed
- No stop in sim exceeds comfort: cmd never below −1.20 (< EMERGENCY_DECEL 3.0 and
  ACCEL_MIN 3.5); identical worst-case to current.
- Lead-distance gating `min(a_settle, −v²/2gap)` untouched — same stopping distance.
- `test_s1.py`: only the 2 constant lines differ; all safety constants intact; py_compile OK.
