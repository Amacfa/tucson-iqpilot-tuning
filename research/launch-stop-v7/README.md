# launch-stop-v7 — L2 + S2 offline candidates (NOT INSTALLED)

Two candidates built 2026-10-02; **both INSTALLED 2026-10-02T03:16Z** (user-approved; `--verify-installed` passed — see `candidates/INSTALL_LOG.md`).

## L2 — launch standstill cap (INSTALLED)
`carcontroller.py` (base = installed L1c `d3915221`): caps accel request at
1.0 m/s² while `CS.out.standstill`. Evidence: brake-release launches at cmd ~2.0
produced measured peaks 2.6–3.8 m/s²; gentler releases (1.28–1.65) peaked
1.8–2.5. Prediction ~2.0–2.3. Package: `candidates/launch-L2/package`.

## S2 — stopped-lead distance (INSTALLED)
`long_mpc.py` (base stock `2b6c5057`): `STOP_DISTANCE 3.0→4.0`. Measured
stopped-lead gaps in routes 3e–42 were 1.8–3.0 m vs the 3.0 constant; expected
+1.0 m. Side effect: +1 m MPC following margin at all speeds (small vs
t_follow·v). Independent of other packages. Package: `candidates/stopdist-S2/package`.

Both: `physical_test_pending` — rollback restores base bytes exactly
(`manage.py --rollback`, parked only).
