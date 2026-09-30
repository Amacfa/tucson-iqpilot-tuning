# tune v5 — FF table refit 12–25 m/s (layered over v4, release 3736edc)

Single-file delta on `iqpilot/selfdrive/controls/lib/latcontrol_torque.py` vs the v4
candidate (pre-state sha256 `9979c41b…` = currently installed v4 file):

`LAT_ACCEL_FACTOR_SPEED_TABLE` row: `[8,12,15,25] -> [2.95,3.20,3.80,3.90]` becomes
`[2.95,3.45,4.05,4.05]` — **+7.8% at 12 m/s, +6.6% at 15, +3.8% at 25**. Everything
else byte-identical to v4 (kp_scale 0.7/0.6, H1 friction LP, request-buffer path).

## Rationale

v4 drive tracking detail (`v4_followup.py`, undelayed reference): mid-band steady
frames at 10–16 m/s track **1.14–1.18** with **negative signed p** — feedforward
over-produces and P/I trim it back, i.e. latAccelFactor still under-scaled in that
range. Scaling the table by ≈ the measured ratio: 3.80×~1.07 ≈ 4.05 at 15; 3.20×~1.08
≈ 3.45 at 12. The **25 m/s breakpoint (+4%) is least-supported** — few high-speed
samples; raised only to keep the table monotonic, re-fit after the next drive.
kp_scale deliberately untouched: the only sub-threshold wobble candidate was P-led
at 6 m/s, so raising low-speed P would be wrong.

## Prediction (open-loop replay on v4 drive frames, 10–20 m/s)

See RESULTS — mid-band steady tracking predicted ~1.03–1.06 vs measured 1.14–1.18;
exit-window torque delta ≤ ~0.01 (higher K shrinks torque for the same lat-accel
command). Sims (handback, curve-exit) neutral: excitation bands unchanged ±~1%.

Caveat: closed-loop P/I currently absorb part of the over-scale, so on-road residual
will be nonzero — iterate with drives.

Install order: tune-v3 → H1 → v4 → **v5** (replaces file) → D1. Rollback restores the
v4 candidate file. `manage.py --check | --apply | --rollback | --verify-installed`
(parked only). Not installed.
