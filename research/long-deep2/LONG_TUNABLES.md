# LONG_TUNABLES — remaining longitudinal/gas knobs on the Tucson (3736edc)

Scope: post-L1c/C1 inventory. Offline only; nothing installed. Hyundai Tucson 4th-gen
CAN-FD, `openpilotLongitudinalControl=True`, camera-SCC. Device state at survey:
ExperimentalMode=off, LongitudinalPersonality=1 (see drift note), L1c+C1 installed,
KARNBIRRLV2 active.

Safety boundary (never touched): `iqdbc/car/interfaces.py` `ACCEL_MIN=-3.5`,
`ACCEL_MAX=2.0`; panda hyundai safety limits; carcontroller's own
`accel = clip(actuators.accel, ACCEL_MIN, ACCEL_MAX)` at carcontroller.py:413 —
all candidates below stay inside these.

---

## 1. longcontrol.py — speed PID + stop state machine

| knob | code | today | verdict |
|---|---|---|---|
| kp (speed-error P) | `interface.py:216` `kpBP=[0], kpV=[1]`, `longcontrol.py:19,26` — Hyundai runs **speed-error** PID (`speed_error_pid=True`): `error = v_target_now − vEgo`, kp=1 | measured: P rms ≤0.22 m/s² vs aTarget rms 0.34–1.06 (LONG_OFFLINE_REPORT §1) — P is a small correction | **leave** — already minimal; raising risks injecting vEgo noise |
| ki | `longitudinalTuning.kiBP/kiV` (empty → 0) | no integrator; steady-state error handled by feed-forward path | **leave** |
| kf | `interface.py:218` `kf=1.0` | feed-forward on aTarget | **leave** |
| stop state machine | `longcontrol.py:36–68`: stopping↔pid gates; `release_blocked` on brakePressed/standstill | works; no fault evidence | leave |
| `stopAccel` | `interfaces.py:258` = **−2.0** | post-standstill hold ramp −0.33→−1.32 invisible in aEgo (STOP_TAPER) | **leave** (no evidence) |
| `stoppingDecelRateOverride` | `longcontrol.py:23` default 1.0, **ABSENT** on device | same — no evidence | leave |
| `DEFAULT_STOPPING_SPEED` | `drive_helpers.py:15` = 0.25 m/s — when should_stop flips | combined with `smooth_stops.settle` | see S1 below |

## 2. Planner side — longitudinal_planner + long_mpc

| knob | code | today | notes |
|---|---|---|---|
| cruise accel envelope | `longitudinal_planner.py:24` `A_CRUISE_MAX_VALS=[2.0,1.6,0.8,0.6]` bp `[0,10,25,40]` | drives the "climb to set" rate; **measured**: capped share 0.33→0.019 after e2e-off, gap med 0.51 m/s (route 32) | now behaving; raising 0.8→~1.0 at 15–25 m/s would firm highway catch-up — moderate evidence, low risk |
| `A_CRUISE_MIN` | :26 = **−1.2** | planner-side decel floor for cruise target | leave (MPC decel dominates real braking) |
| `J_CRUISE` | :27 = **1.0 m/s³** rate-limit on cruise accel | launch gentleness partly comes from here | tunable — see §6 |
| `LAUNCH_MAX_ACCEL` | :35 = 1.5 | v4/v5 launches a_pk ~2.4–2.5 (car overshoots cmd — SCC jerk window, not planner) | leave planner; see §3 |
| e2e path | `get_e2e_accel` E2E_CRUISE_ACCEL_MAX=0.5, TAU=15 | **dead code** while ExperimentalMode=off | no-op now |
| MPC weights | `long_mpc.py:37–42` J_EGO=20 × jerk_factor | jerk_factor: std/relaxed 1.0, aggressive 0.5 (:61) | personality=1 → full jerk penalty already |
| `get_T_FOLLOW` | :72 — rel 1.75 / **std 1.45** / agg 1.25 | sets MPC follow distance + `desired_dist_comfort` | tunable (see below) |
| `COMFORT_BRAKE` | =2.5; `LEAD_PULLAWAY_VREL` 0.5, `ABRAKE` −0.5; `MIN_X_LEAD_FACTOR` 0.5; `STOP_DISTANCE` 3.0; `LEAD_DANGER_FACTOR` | stock upstream values | leave — no evidence of lead-cut-in problem in v5 drives |
| lead handling | `process_lead`/`process_lead_legacy` :190+ — model+radar fusion w/ `new_lead_mpc` toggle | healthy; reaction lag not separable from model latency in exports | leave |

## 3. Hyundai CAN-FD carcontroller — SCC command shaping

`carcontroller.py:748–811` `HyundaiJerk.make_jerk`, CAN-FD branch:
- `jerk_u = max( clip(1.0 + 2·(accel−1), 1.0, 5.0),  clip(mpc_jerk·2, 1.0, 5.0) )`
- `jerk_l = max( clip(1.2 + 2·(−accel−2.8), 1.2, 5.0), clip(−mpc_jerk·4, 1.2, 5.0) )`
- **L1c already installed** — the launch-eagerness fix (caps the `jerk_u` ramp allowance
  that the Tucson's SCC treats as a ramp *rate*; evidence: baseline a_pk 1.54/cmd 2.0 →
  v2-era overshoot 2.2–4.3 → v5 launches now a_pk 0.22–1.75 with cmd 0.66–1.75, gentle).
- `jerk_l_base = 1.2`, boost ≥2.8 m/s² decel — untouched by L1c; stop-taper feel lives
  partly here (car delivers only 30–60% of −0.5 m/s² request <1 m/s — creep torque).
- `CanfdStopping` state machine (`stopping.py`, `CanfdStopRetry=0` on device) — off;
  entry speed 0.7, stop band 0.20, retry window 3 s. Experimental; leave off.
- `SpeedFromPCM=2`, `CarrotCruise*` = −1 (inactive), `carrotCruise` gating on
  `CS.out.carrotCruise>0` — inactive paths.
- aReqValue quantization: not observed as a problem; no evidence.

## 4. IQ params — device values + consumer status

| param | device | consumer | verdict |
|---|---|---|---|
| `LongitudinalPersonality` | **1 (re-applied; reverted to 2 at boot twice — user should set UI once)** | `long_mpc.py` T_FOLLOW/jerk_factor | live |
| `IQGasOverrideBoost` | 0 (off) | `longitudinal_planner.py:143` → `AccelBoost` (+1.0 m/s² ramp on held gas >10 mph) | live; candidate below |
| `EnableLongComfortMode` | 1 | `controlsd.py` → `carControl.longComfortMode` → Tesla/VW only | **no-op on Hyundai** |
| `IQCustomStopDistance` | 2 | `custom_stop_distance.py` (stop-distance offset vs model plan) | live; e2e-adjacent |
| `IQE2EDistanceControl` | 1 | `E2EDistanceController` | live when e2e on; idle now |
| `IQForceStops` | 1 | `smooth_stops.settle` enabled | live — the stop taper |
| `CanfdStopRetry` | 0 | `carcontroller.py:190` → `CanfdStopping` | off, experimental |
| `stoppingDecelRateOverride` | absent | `longcontrol.py:23` default 1.0 | dormant knob |
| `LongitudinalManeuverMode` | absent | manager process_config (dev maneuver testing) | leave absent |
| `SpeedFromPCM` | 2 | carcontroller speed source | leave |
| `IQLongLearnedFactors` | absent | `card.py` learned-factor persistence | dormant |
| `IQToyotaFactoryLong` | 0 | Toyota-only | **no-op on Hyundai** |
| `CarrotCruise(Decel|AtcDecel)` | −1 | hyundai carcontroller carrot-cruise decel | inactive |
| `SpeedLimitController`/`SLCSetSpeedToLimit`/`EnableSpeedLimitControl`/`VisionCurveSpeedController`/`MapCurveSpeedController`/`IQSpeedAssistMode`=1/slc_* | off/display | verified inert earlier (SETTINGS_AUDIT) | leave off |
| `DisengageOnAccelerator` | False | cruise override — gas keeps engagement | live; keep |
| `IQE2ESetSpeed*` | dead while ExperimentalMode off | `cruise.py` e2e gate | dormant |
| `expSpeedConv` | True | e2e convergence | dormant while e2e off |

## 5. Drive evidence (measured; exports + this survey's scan)

| metric | baseline (stock) | v2 stack | v4 | **v5+L1c+C1** |
|---|---|---|---|---|
| launch a_pk median | 1.54 | 2.2 | 2.41 | **~0.22–1.75, cmd ≤1.75** (L1c working — gentle launches) |
| launch cmd_pk | 2.0 | 1.78 | 2.0 | 0.66–1.75 |
| stops: a_min med | −0.57 | −1.17 | −1.57 | n/a (stop detector thin on new routes; ~1,685 baseline + 1,767 v2 stops analyzed in STOP_TAPER) |
| set-speed gap med (engaged, no lead) | n/a (pcmCruise) | 2.5 | 4.22 (e2e cap) | **0.51–0.03** — cruise reaches set now |
| gas override frames | 65,071 | 34,942 | 12,191 | 1,077 (2 routes) |

Stop-taper measured facts (STOP_TAPER, still valid — smooth_stops unchanged): car
delivers 30–60% of −0.5 m/s² below 1 m/s; last 1 m/s takes ≥4 s in 24/28 stops;
46% have ≥0.5 s stall; final nod −0.35 med (mild). Gas-override context: v5 drives
1077 frames over ~14 min engaged ≈ 1.3/min — down from v4's ~12/drive events.

## 6. Ranked candidates

| # | change | evidence × confidence × risk | sim |
|---|---|---|---|
| **1. S1 stop taper** (`smooth_stops.py`: `SETTLE_DECEL 0.80→1.00`, `TAPER_SPEED 1.0→0.6`) | **strong measured problem** (4+ s crawl, 46% stalls, creep overpowering) × high confidence × low risk (same kiss, lead-gating unchanged) | replay stop windows vs fitted plant; predict t(1 m/s→0) ≈1.5–2 s vs ≥4 s |
| **2. `IQGasOverrideBoost` → True** (param only — L1c interacts: boost raises accel request which feeds `jerk_u_raw`; verify cap holds) | user gas-overrides ~1.3/min on v5 drives × medium × low (reversible param) | replay gas-press frames, check `jerk_u` stays under L1c cap |
| **3. `A_CRUISE_MAX_VALS` 0.8→1.0 at 15–25 m/s** (`longitudinal_planner.py:24`) | residual median gap 0.51 m/s is fine but catch-up is soft at highway speeds × medium × low | cruise-accel replay on route 32 climbing intervals |
| **4. `jerk_l_base` 1.2→1.5 + stronger creep counter at <1 m/s** (carcontroller HyundaiJerk CAN-FD branch) | same stop-crawl evidence; firmer decel authority below 1 m/s × medium × medium (CAN-shaping, needs parked sim + careful A/B) | fit_plant decel-response model on the 28 baseline stops |
| **5. `J_CRUISE` 1.0→1.2** | smoother-but-slower accel ramp; weak felt problem now × low | replay launch/climb windows |

**Boundary list (do not touch)**: `ACCEL_MIN/MAX` (−3.5/+2.0), `jerk_max_u/l=5.0`
(SCC hard cap), panda hyundai long safety limits, `LEAD_DANGER_FACTOR`,
`DANGER_ZONE_COST`, `EMERGENCY_DECEL`, `MIN_X_LEAD_FACTOR`, `E2E_STOP_MIN_DIST`.

**Watch item**: `LongitudinalPersonality` reverts to 2 at reboot (2× observed) —
user should set Standard in the comma UI once to persist it; hourly drift check
already flags it.
