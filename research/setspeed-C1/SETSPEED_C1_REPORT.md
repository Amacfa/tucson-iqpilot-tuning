# C1 — set-speed re-engage fix (not installed)

## Evidence: stale set speed after re-engaging with SET (release 3736edc)

| route | T (s) | vEgo (m/s) | stale set (m/s) | min accel after engage | driver response |
|---|---|---|---|---|---|
| 28 | 258.2 | 20.5 | 11.11 | -1.46 | gas override |
| 2c | 349.2 | 14.45 | 10.11 | -1.60 | gas override |
| 25 | 152.6 | 13.4 | 10.0 | -0.44 | gas override |
| 24 | 127.0 | 9.45 | 8.67 | -0.93 | — |

Source: drives/long3/long3b_attrib.json `engages` per route.

## Root cause

`VCruiseHelper.initialize_v_cruise` (iqpilot/selfdrive/car/cruise.py ~line 347) early-returns
on `self.v_cruise_initialized`, so every re-engagement keeps the previous set speed regardless
of the button used. Upstream openpilot re-initializes on every engage (SET -> current speed,
RES -> last set speed).

## Diff (work/forward.patch, authored change — logic unchanged)

- `if self.CP.pcmCruise or self.v_cruise_initialized: return` split:
  - re-engagement + SET/decelCruise -> `v_cruise_kph = clip(vEgo*MS_TO_KPH, v_cruise_min, V_CRUISE_MAX)`
  - re-engagement + RES/accelCruise -> `v_cruise_kph_last`
  - re-engagement + no button -> unchanged; cluster follows set speed either way
  - first engagement path untouched (V_CRUISE_INITIAL=40 floor).

## Validation (validation/test_c1.py, all_passed=true)

- first engage 4.44 m/s + decelCruise: stock == candidate == 40 kph (V_CRUISE_INITIAL floor)
- stale 40 kph, re-engage @20.5 m/s SET: candidate 74 kph, stock 40 kph
- re-engage resumeCruise: 40 kph (last kept)
- re-engage no buttons: 40 kph unchanged
- SET re-engage @2 m/s: floored to v_cruise_min=8
- cluster follows set speed
- py_compile OK; forward/reverse patch roundtrip byte-identical;
  test_artifacts + test_manage transaction suite green (7 guards).
- Stubbing disclosure: no capnp locally — iqpilot.cereal car/custom enums, Params,
  long_increments, CV constants, iqdbc.car.structs stubbed; cruise.py loaded from
  the actual package files, no logic copied.

## Device hash check

`/data/openpilot/iqpilot/selfdrive/car/cruise.py` sha256 =
`5dea5d192208cc07039cb2412249fbb12d89d1a0061dd5ad898d1d823662a298` — matches
`cruise.orig.py` exactly (verified read-only). Note: device path is
`iqpilot/selfdrive/car/cruise.py`, not `selfdrive/car/cruise.py`.

## Install / rollback (NOT run)

```
cd /data/tucson_stage/setspeed-3736edc-C1/package
PYTHONPATH=/data/openpilot/.venv/lib/python3.12/site-packages:/data/openpilot \
  /data/openpilot/.venv/bin/python manage.py --check
  /data/openpilot/.venv/bin/python manage.py --apply
  /data/openpilot/.venv/bin/python manage.py --rollback
```
Candidate sha256: `1abb8a1e00c3a301d54d07ceb2a2fcf80777a0337507d63a405b3a7d4328e940`
