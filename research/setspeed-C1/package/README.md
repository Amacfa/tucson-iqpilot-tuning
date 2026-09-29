# tucson-setspeed-3736edc-C1 — set-speed re-engage fix

Status: check_only. NOT installed. Base = stock 3736edc cruise.py (no layering).

Single target file: `iqpilot/selfdrive/car/cruise.py`
(`VCruiseHelper.initialize_v_cruise`, ~line 347).

Problem: stock IQ early-returns `initialize_v_cruise` whenever `v_cruise_initialized`
is true, i.e. on every re-engagement the last set speed is kept even when the driver
presses SET. Four logged events (release 3736edc) show the car braking toward a stale
set speed below current speed after re-engaging with SET, prompting gas overrides.
Upstream openpilot re-initializes on every engage (SET → current, RES → last).

Change (authored elsewhere, logic unchanged here): on re-engagement —
- SET/decelCruise: v_cruise_kph = clip(CS.vEgo * MS_TO_KPH, v_cruise_min, V_CRUISE_MAX)
- RES/accelCruise/resumeCruise: keeps v_cruise_kph_last
- no button events: unchanged
- v_cruise_cluster_kph follows either way
- first engagement (v_cruise_kph == UNSET): identical to stock.

manage.py: same transaction semantics as the tune-v2/L1c managers
(--check/--apply/--rollback/--verify-installed, hash verification, parked() gate,
atomic replace + backup). Nothing here restarts services.

Validation: validation/test_c1.py — VCruiseHelper instantiated from both stock and
candidate files (cereal/params/structs stubbed; no capnp on this box), 6 cases:
first-engage identical (both give V_CRUISE_INITIAL=40), SET re-engage 20.5 m/s →
74 kph vs stock 40, RES keeps last, no-buttons unchanged, SET floor at v_cruise_min,
cluster follows. Plus py_compile and patch roundtrip.
