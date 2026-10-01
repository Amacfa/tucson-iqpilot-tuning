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
| ~~`LongitudinalPersonality`~~ | 2 (**relaxed**) | ~~1~~ **ERROR — enum misread** | cereal enum is aggressive=0 / standard=1 / relaxed=2; value 2 was the user's intended Relaxed mode (T_FOLLOW 1.75 s, gentlest). This change is **superseded** — param left at 2; do not re-apply 1 |
| `LaneChangeBsd` | 0 | **1** | blind-spot veto enabled on auto lane changes |

Post-write re-read verified (`repr`: `1`, `1`). Full params diff vs post-round-1 dump: only
these two keys changed (plus the `ModelManager_LastSyncTime` timestamp as before).

### Rollback (round 2)

```bash
cd /data/openpilot && PYTHONPATH=.venv/lib/python3.12/site-packages:. .venv/bin/python -c "
from iqpilot.common.params import Params; p = Params()
p.put('LongitudinalPersonality', 2)   # NB: 2 == relaxed = the user's intended value; rollback also restores 2
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

## Erratum — LongitudinalPersonality enum was misread (2026-09-30)

The cereal enum is aggressive=0 / standard=1 / **relaxed=2** — reversed from what this
document assumed. Value 2 is **Relaxed**, the mode the user actually selected in the UI
(T_FOLLOW 1.75 s — the longest, gentlest profile). Consequently:

- The repeated "revert to 2" was **not drift**: the UI/car re-writes the user's chosen
  Relaxed at every boot, correctly restoring 2.
- Every re-application of `1` (standard) above was an error on our side; the device has
  now been left at **2** and hourly `EXPECTED_PARAMS` expects `2`.
- The recommendation to "set Standard in the UI" is withdrawn — the user's UI selection
  is Relaxed and it persists correctly on its own.
- All analyzed drives (routes 2f/30/32/33) logged `selfdriveState.personality=relaxed`
  for every frame — no drive has ever run on standard in this dataset.

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
