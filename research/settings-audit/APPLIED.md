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
