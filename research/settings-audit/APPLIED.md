# Settings applied on-device — 2026-09-30 (user-approved, parked, IsOffroad=1)

Set via `Params().put_bool()` (same API the UI uses) — no file edits, no service restarts.

| param | before | after | effect |
|---|---|---|---|
| `ExperimentalMode` | True | **False** | exits e2e longitudinal — car now follows set speed via `get_cruise_accel` (plan source `cruise`, not `e2e`) — fixes the "won't climb to set speed" |
| `LongIncrementsEnabled` | False | **True** | hold RES/SET = ±5 mph steps (`LongIncrementHoldStep=5`), tap = ±1 |
| `IQE2ESetSpeedUseCurrent` | True | **False** | **inert while ExperimentalMode=False** — `cruise.py initialize_v_cruise` gates `get_iq_mode_initial_set_speed_kph` on `experimental_mode` (param-read in card.py); with e2e off, engage set speed = `clip(vEgo, 40 kph, max)` = current speed (stock). Would only matter if ExperimentalMode is re-enabled (then initial set = fixed `IQE2ESetSpeedMph`=65, **not** current speed — re-flip UseCurrent first if that's undesired) |
| `EnableLongComfortMode` | False | **True** | **no-op on this car** — `carControl.longComfortMode` is consumed only by Tesla/VW carcontrollers; the Hyundai path ignores it. Set anyway per approval |

Verification: re-read all four post-write on device — all correct. Full params diff vs
pre-change dump: only the four keys changed (`ModelManager_LastSyncTime` timestamp also moved —
background bookkeeping, not user-facing).

## Round-2 additions (same session, int-encoded via `Params().put`)

| param | before | after | effect |
|---|---|---|---|
| `LongitudinalPersonality` | 2 (aggressive) | **1 (standard)** | `long_mpc.py` T_FOLLOW 1.25→1.45 s, jerk_factor 0.5→1.0 — longer following gap, gentler lead tracking |
| `LaneChangeBsd` | 0 | **1** | blind-spot veto enabled on auto lane changes |

Post-write re-read verified (`repr`: `1`, `1`). Full params diff vs post-round-1 dump: only
these two keys changed (plus the `ModelManager_LastSyncTime` timestamp as before).

### Rollback (round 2)

```bash
cd /data/openpilot && PYTHONPATH=.venv/lib/python3.12/site-packages:. .venv/bin/python -c "
from iqpilot.common.params import Params; p = Params()
p.put('LongitudinalPersonality', 2)
p.put('LaneChangeBsd', 0)
"
```

## Rollback

```bash
cd /data/openpilot && PYTHONPATH=.venv/lib/python3.12/site-packages:. .venv/bin/python -c "
from iqpilot.common.params import Params; p = Params()
p.put_bool('ExperimentalMode', True)
p.put_bool('LongIncrementsEnabled', False)
p.put_bool('IQE2ESetSpeedUseCurrent', True)
p.put_bool('EnableLongComfortMode', False)
"
```

`hourly/refresh.py` now carries `EXPECTED_PARAMS` — any drift on these four is flagged in
`device_facts.param_drift` and report warnings on every hourly tick.

## Re-application note (2026-09-30, post-L1c/C1 install)

`LongitudinalPersonality` was found reverted to `2` at the v5-drive ingest (param_drift
flagged by hourly) and **again after the install reboot** — the value does not appear to
persist across reboot. Re-applied `1` (Standard) via `Params().put`; readback `1` and the
hourly drift check is clean. If it keeps reverting, suspect the UI writing the last-chosen
driving mode at boot rather than param loss — recommend the user set Personality =
Standard in the comma UI once so the UI state agrees.

## Pending — IQGasOverrideBoost (NOT applied, 2026-09-30)

Finding from code (device 3736edc): `longitudinal_planner.py:224–225` —
`output_a_target_e2e = modelV2.action.desiredAcceleration + accel_boost` — the boost
(+1.0 m/s² max ramp, `accel_boost.py` ACCEL_BOOST_MAX=1.0, RATE=0.1, ≥10 mph) is added
**only to the e2e candidate**. `get_accel_candidates` only includes the e2e candidate
when `is_e2e` is true → **while `ExperimentalMode=False` (current state) the param is a
complete no-op**, same class as `EnableLongComfortMode`. If e2e is ever re-enabled:
boost raises the accel request, which feeds `jerk_u_raw` in `HyundaiJerk.make_jerk` —
the **L1c jerk cap still applies** (`carcontroller.py:803` `jerk_u_raw = clip(1.0+2·(accel−1), base, jerk_max_u)` and `:806` max-vs-mpc; L1c caps the resulting jerk_u).

Apply (when wanted, parked):
```bash
p.put_bool('IQGasOverrideBoost', True)
```
Rollback: `p.put_bool('IQGasOverrideBoost', False)`
