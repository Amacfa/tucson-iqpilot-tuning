# tune H1 — lane-change handback fix (layered over tune-v3, release 3736edc)

Single-file delta on `iqpilot/selfdrive/controls/lib/latcontrol_torque.py` vs the tune-v3
candidate (pre-state sha256 `277aff99…` = installed tune-v3 candidate):

1. **P gain ×0.6 above ~15 m/s**, smooth interp `interp(vEgo, [13,17], [1.0,0.6])`
   (scales the `_k_p` table per frame; base table preserved in `self._kp_base`).
2. **0.3 s first-order LP on the friction-compensation error input**
   (`self._fric_err_lp` feeds `get_friction` instead of raw `error`), mirroring
   sim_handback `friction_tau=0.3`.

Evidence: `analysis/wobble/sim_friction.py` — on the route-26-seg-6 handback excitation with
the v3 table, Fix C ≈ halves the excursion: ala_pp 1.033→0.507, 1–3 Hz band 0.929→0.629,
track_rms 0.297→0.098. Re-run with the exact H1 shaping (interp 13→17) reproduces 0.507.

Install order: tune-v3 → **H1** → D1. Rollback restores the tune-v3 candidate file.
`manage.py --check | --apply | --rollback | --verify-installed` (parked only). Not installed.
