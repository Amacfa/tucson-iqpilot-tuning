# tucson-cruise-3736edc-E1 — cruise usability: engage=current speed, turn accel budget, set-drop coast

Status: check_only. NOT installed. Layered on two existing candidates (see rebase_note in manifest.json).

Two target files:
- `iqpilot/selfdrive/car/cruise.py` (base = C1 candidate, sha256 1abb8a1e00c3…)
- `iqpilot/selfdrive/controls/lib/longitudinal_planner.py` (base = A3 candidate, sha256 d6abce2e969e…)

## What the driver feels

- **Engaging always sets the cruise to the speed you're actually doing** — rounded to the
  nearest 5 mph (or 5 km/h in metric), never below 25 mph. Same result whether you press
  SET, RES, + or −, on first engage and every re-engage. No more surprise 65-mph resume
  targets and no more waking up to a stale set speed.
- **In a hard turn the car no longer keeps pushing gas** — the same lateral-accel budget
  that already limits acceleration in non-e2e driving now also applies in e2e mode, with a
  0.3 m/s² floor so it still creeps through intersections.
- **Lowering the set speed while cruising gently over it no longer brakes hard** — for a
  few seconds after you drop the set speed, if you're less than ~10 mph above it with no
  lead car and no stop pending, deceleration is limited to a −0.5 m/s² coast-down instead
  of a firm brake. Outside that window the car brakes exactly as before — the coast only
  applies right after a set-speed drop, never to model stops.

## The three changes

1. **cruise.py — `IQ_ENGAGE_AT_CURRENT_SPEED` gate** (module constant, `True`): inside
   `initialize_v_cruise`, when the car is not pcmCruise, the engage speed becomes
   `max(vEgo, ENGAGE_FLOOR_KPH=40)` rounded to the 5 mph/5 kph display step, clipped to
   `[v_cruise_min, V_CRUISE_MAX]`; cluster follows. `self._is_metric` is captured at the
   top of `update_v_cruise` (init `False` in `__init__`). With the flag `False` the C1
   code path is byte-for-byte unchanged.
2. **longitudinal_planner.py — e2e turn-accel budget**: the `if not e2e:` guard on the
   lateral-accel budget is removed, so `a_x_allowed` is computed and applied in e2e mode
   too; `E2E_TURN_ACCEL_FLOOR = 0.3` keeps a minimum creep accel while turning.
3. **longitudinal_planner.py — set-drop coast**: a 5 s `SET_DROP_COAST_TIME` window opens
   whenever the cruise target is lowered (`v_cruise < prev − 0.1 m/s`); it is cleared on
   disengage (`reset_state`). After the `output_should_stop` lines and before the
   mode-blend block, while that timer is live and e2e has no lead, no pending stop and no
   FCW, and `0 < v_ego − v_cruise < SET_DROP_COAST_GAP (4.5 m/s)`, the accel target is
   floored at `SET_DROP_COAST_ACCEL = −0.5 m/s²`. The timer gate is the safety fix: model
   braking (stop signs, pedestrians) is unaffected because those events don't lower the
   set speed.

## Rollback

```
python3 manage.py --rollback
```

(restores both files to their pre-apply bytes from `rollback/`; same transaction
semantics as the other packages — hash verification, parked() gate, atomic replace.)

## What remains unvalidated

Pure-function and replay checks pass (below), but **none of this has run on the road**:
real e2e turn behaviour at speed, engage rounding vs the dashboard step, and coast-gap
interactions with mpc transitions all need a physical drive. `physical_validation_pending: true`.

## Validation performed

- `validation/test_e1_cruise.py` — 13 checks, all pass. Imperial: 19 mph → 25 (floor),
  36 → 35, 2 mph crawl → 25, 33 mph re-engage w/ resumeCruise + initialized → 35
  (not 65, not last), 47 → 45; metric 52 kph → 50; cluster == v_cruise; flag off →
  C1 cases identical.
- `validation/test_e1_planner.py` — e2e hard turn (v=5.8, angle=117°) first step
  ≤ 0.3 + J_CRUISE·dt and never exceeds 0.3 over 3 s of iterated calls; angle=0 ramps
  normally; non-e2e results identical to the A3-base original on a grid. update()-level
  timer cases: 40→30 mph drop then ~1 s of frames → output floored at −0.5 m/s²; same
  speeds with no drop → floor inactive (−1.4 passes through); >5 s after the drop →
  timer expired, floor inactive; disengage (vCruise UNSET) zeroes the timer.
- `validation/test_e1_replay.py` — replay on exported segs 00000048-4/5:
  turn window T 314–325 s: 85 % of cap-binding frames (a_x < 1) had logged accel above
  the new cap, max reduction 1.68 m/s², mean 0.90; set-drop window T 350–358 s: logged
  min −1.425 within the coast-gap band is raised to the −0.5 floor.
- `test_manage.py` (7 transaction guards) and `test_artifacts.py` (hashes, patch
  roundtrip, py_compile of both trees) — all pass.
