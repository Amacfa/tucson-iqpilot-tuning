# tune D1 — lookahead-delay cap while lagd is unestimated (layered over H1, release 3736edc)

Single-file delta on `iqpilot/selfdrive/controls/controlsd.py` (pre-state sha256
`1cdb4917…` = live device file, verified read-only). Does NOT touch latcontrol_torque.py
(H1 owns that file), lagd, or the LiveDelay param.

## Why
lagd has never estimated on this car: `LiveDelay` param = lateralDelay 0.30 s,
status `unestimated`, calPerc 0. The 0.30 s is lagd's `initial_lag = CP.steerActuatorDelay + 0.2`
(lagd.py:182). For torque cars `lateral_action_delay` returns the live value
(steer_delay.py), so the request-buffer lookahead in `LatControlTorque.update`
(`delay_frames = lat_delay/dt`, controlsd.py:271→276) runs at 0.30 s. Measured
torque→d(ala)/dt lag on this car is ~0.03–0.05 s (DELAY_FIT.md).

## Change
```python
if (self.CP.carFingerprint == "HYUNDAI_TUCSON_4TH_GEN"
    and self.sm["lateralDelay"].status == log.LateralDelay.Status.unestimated):
  lat_delay = min(lat_delay, 0.15)
```
Single consumer site — there is no get_lag_adjusted_curvature in this release; the only
lat_delay consumer in the lateral path is latcontrol_torque's request-buffer lookahead.
Gated on `unestimated` so a real lagd estimate (estimated) or invalid passes through, and
other fingerprints are untouched.

## Alternative
If 0.15 s still looks laggy in drive data, next step is 0.10 (= steerActuatorDelay) — same line.

Rollback restores controlsd.py to hash `1cdb4917…`. `manage.py` usage identical. Not installed.
