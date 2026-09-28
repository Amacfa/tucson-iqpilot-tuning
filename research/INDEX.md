# Hourly research reports

- [20260928T044855Z](20260928T044855Z.md)

## Drive 1 (route 00000024--<redacted>, post-install 3736edc, tune v1 + arming + fingerprint)

- [drive1/SIM_REPORT.md](drive1/SIM_REPORT.md) — closed-loop curve-exit sim: measurement LP removal effect
- [drive1/WOBBLE_REPORT.md](drive1/WOBBLE_REPORT.md) — post-curve 0.5-3 Hz wobble metrics, faults/event timeline, tune-active verification
- [drive1/DRIVE1_INPUTS.md](drive1/DRIVE1_INPUTS.md) — sim input tables: npz fields, torque→latAccel gain fits, lateralDelay stats, IQ param inventory
- [drive1/sim_curve_exit.py](drive1/sim_curve_exit.py), [drive1/postcurve_wobble.py](drive1/postcurve_wobble.py) — analysis scripts
- `candidates/tune-v2-3736edc/` — tune v2 package (measurement LP removed; FF schedule + friction 0.12 + jerk_u kept; applies over installed v1 via accepted_current_sha256)
