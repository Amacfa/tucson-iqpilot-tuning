# tucson-long-3736edc-L1c — longitudinal launch jerk cap (layered, reversible)

Status: check_only. NOT installed. software_validation_passed = true (offline only);
physical_validation_pending = true.

Single target file:
`.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carcontroller.py`

This is a LAYERED package: its "original"/rollback bytes are the tune-v2 candidate
(`a8cf776c…`), i.e. exactly what is installed on the device today — NOT stock 3736edc.
`--rollback` therefore restores the tune-v2 state, not factory. Do not apply unless
tune-v2 is installed (or accept that rollback gives you the tune-v2 file, which is
identical in all other respects anyway).

## Change (vs the installed file)

The CANFD `jerk_u` block gains a speed-interpolated cap so the raw-request boost
cannot demand full jerk at launch speeds:

    jerk_u_cap = float(np.interp(CS.out.vEgo, [3.0, 8.0], [1.2, jerk_max_u]))
    jerk_u_raw = np.clip(jerk_u_base + 1.0 * max(0.0, accel - 1.0), jerk_u_base, jerk_u_cap)
    jerk_u_mpc = np.clip(self.jerk * 2.0, jerk_u_base, jerk_u_cap)

and the raw boost gain is reduced 2.0 → 1.0. Effect: below ~3 m/s jerk_u is limited
to ~1.2 m/s^3 (was able to hit jerk_max_u), ramping to full authority by ~8 m/s.
Above 8 m/s the cap is the normal max, but the raw boost is still gentler than the
old 2.0 gain (accel=4 m/s^2 → 4.0 m/s^3 vs 5.0 before). Motivation: drive data
shows the launch surge (peak aEgo 2.2–4.3 vs baseline ~1.9) tracks the tune-v2
jerk_u boost, not the release's new longitudinal PID.

## Validation (validation/test_jerk_cap.py)

Execs the real block text from the candidate file with stub CS/self:
vEgo=0/accel=2.0/jerk=1.5 → 1.2; vEgo=5.5 → 3.0 (cap 3.1); vEgo=10 → 2.0;
vEgo=0/accel=0.5 → 1.0; monotonicity in speed; delta vs the installed file
documented (old gives 3.0/5.0 at those points). Plus py_compile, patch
forward/reverse roundtrip byte-identical, and the package test_manage.py /
test_artifacts.py transaction suite.

manage.py is copied verbatim from tucson-tune-3736edc-v2 (same --check/--apply/
--rollback/--verify-installed semantics, hash verification, parked() gate,
atomic transaction + backups under /data/iq-warning-backups/). No service
restarts are performed by the script itself.
