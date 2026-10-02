# Cruise usability candidate E1 (3736edc) — offline, NOT installed

Package: `package/` — `manage.py --check/--apply/--rollback/--verify-installed`,
hashes verified against the installed bases. Layered over two live candidates:
- `iqpilot/selfdrive/car/cruise.py` — base = C1 candidate, sha256 `1abb8a1e00c3…`
- `iqpilot/selfdrive/controls/lib/longitudinal_planner.py` — base = A3 candidate, sha256 `d6abce2e969e…`

Candidate hashes: cruise.py `9186434f6439…`, longitudinal_planner.py `33788391e05a…`.

## Evidence

- **Fixed-65 engage**: `IQE2ESetSpeedMode=1` makes the first/re-engage jump to a fixed
  65 mph target regardless of actual speed — driver sees a surprise resume speed.
- **Crawl engage**: on route 00000048, engaging at 2 mph produced a 5 mph set — the
  driver crawls, the car targets a crawl.
- **Turn lurch (route 48, T ≈ 314–325 s)**: hard turn, lead gone, gas off — e2e was
  commanding up to ~1.9 m/s² accel at ~160° wheel angle because the lateral-accel
  budget only applied in non-e2e mode. Replay: 85 % of frames where the new cap
  actually binds (a_x < 1) had logged accel above it; max reduction 1.68 m/s²,
  mean 0.90. e2e accel >1.2 m/s² mid-turn appears in 5 of the last 6 drives.
- **Set-drop braking (route 48, T ≈ 350–358 s)**: dropping the set 40→30 mph while
  doing ~36 mph produced a −1.43 m/s² commanded / −1.9 measured decel — a firm brake
  event for a gentle overshoot. Logged min −1.425 within the 0–4.5 m/s overshoot
  band is raised to the −0.5 coast floor by the patch.

## The three changes

1. **cruise.py — engage adopts current speed** (`IQ_ENGAGE_AT_CURRENT_SPEED = True`,
   `ENGAGE_FLOOR_KPH = 40.0`): every engage/re-engage, any button, sets cruise to
   current speed rounded to the 5 mph / 5 kph display step, floor 25 mph. Bypasses
   the IQE2E fixed-65 path and the keep-last path. Flag off → C1 bytes identical.
2. **planner — e2e turn-accel budget**: the `if not e2e:` guard on the lateral
   budget is removed; e2e gets the same `a_x_allowed` cap with a
   `E2E_TURN_ACCEL_FLOOR = 0.3` creep floor.
3. **planner — set-drop coast (timer-gated)**: `SET_DROP_COAST_TIME = 5.0` s window
   opens only when the cruise target is actively lowered (`v_cruise < prev − 0.1`),
   cleared on disengage. Inside it, e2e + no lead + no pending stop + no FCW +
   `0 < v_ego − v_cruise < 4.5 m/s` → accel floored at −0.5 m/s². Model braking for
   stops is untouched — those events don't lower the set speed.

## Validation (all pass, in `package/validation/`)

- `test_e1_cruise.py` — 13 checks: 19mph→25, 36→35, 2→25, 33+resume→35 (not 65/last),
  47→45, metric 52kph→50, cluster==v_cruise, flag-off → C1 identical.
- `test_e1_planner.py` — e2e turn (5.8 m/s, 117°) ≤0.3+J·dt and never >0.3 over 3 s;
  angle=0 ramps; non-e2e identical to A3 base on a grid. update()-level timer cases:
  40→30 mph drop → floored −0.5 within 1 s; no drop → floor inactive (−1.4);
  >5 s later → expired; disengage → timer zeroed.
- `test_e1_replay.py` — the replay numbers quoted above (asserts pass).
- `test_manage.py` (7 guards), `test_artifacts.py` (hashes, patch roundtrip,
  py_compile) — all pass.

Not road-validated: `physical_validation_pending: true`.
