# tucson-tune-3736edc-S1 — smooth-stop taper S1

Single-file delta over the installed stack (v5 + D1 + L1c + C1) on release `3736edc`.

## Change

`iqpilot/selfdrive/controls/lib/smooth_stops.py`:

```
SETTLE_DECEL  0.80 -> 1.00
TAPER_SPEED    1.0 -> 0.6
```

Holds ~−1.0 m/s² commanded (≈ −0.6 delivered on this car, per STOP_TAPER measurements)
down to 0.6 m/s, then tapers to the same −0.25 m/s² kiss. Predicted crawl from 1 m/s to
standstill ≈ 1.5–2.9 s vs ≥4 s measured. Lead-gap limiting (`STOP_GAP_MARGIN`,
`MIN_GAP_BUDGET`), `ANTI_CREEP_RATE`, `SETTLE_JERK`, `EMERGENCY_DECEL` and
`ACCEL_MIN/MAX` are byte-identical — stopping distance behind a lead cannot shorten.

## Install order / rollback

After tune-v5 → D1 → L1c → C1. Rollback (`manage.py --rollback`, parked) restores
`b0ba5983` (stock smooth_stops). Backup recorded in `/data/iq-warning-backups/`.

## Status

Built + sim-validated 2026-09-30. **Not installed.**
