# IQ settings audit — speed-cap cause + smooth-driving settings (release 3736edc)

Read-only: full Params dump taken, nothing changed. Secret-shaped keys skipped.

## (a) Why the car won't climb to the set speed — **E2E model speed plan**

**Dominant cause (verified in drive data): ExperimentalMode longitudinal.** `ExperimentalMode=True` +
`ExperimentalModeConfirmed=True`, so `LongitudinalPlannerIQ.is_e2e` is true every drive and
`longitudinalPlanSource = 'e2e'`. In e2e the accel target = `modelV2.action.desiredAcceleration`;
the only thing pulling the car toward the set speed is `get_e2e_accel`'s convergence term
`min((v_cruise−v_ego)/15.0 s, 0.5 m/s²)` (`E2E_CRUISE_CONVERGENCE_TAU=15`, `E2E_CRUISE_ACCEL_MAX=0.5`,
`expSpeedConv=True`) — and only when the model isn't already accelerating harder. If the vision
model *plans* a slower speed (its `speeds` trajectory ≈ v_ego), the car just cruises there.

**Drive data** (export-v3b frames, engaged + lon-active + pid state, v>8 m/s, no lead, |a|<0.3,
set−actual > 3 m/s):

| group | capped frames | dominant lps | share | example |
|---|---|---|---|---|
| v4 (route 2e) | ~9007 | `e2e` | ~99.9% | set 20.0, v 13.75, plan v[0]=13.75, acc −0.02 — model plans 13.75 |
| v3h1d1 (2d) | ~1360 | `e2e` | ~99% | set 16.89, v 13.77, plan v[0]=13.77 |
| v2 (25+28) | ~412 | `e2e` | ~100% | set 21.3, v 16.3, plan v[0]=16.5 |

No single contiguous >15 s run — accel flickers ±0.3 so runs fragment — but the gap is persistent
and, critically, `lpv` (planner speed trajectory) sits **at** v_ego, i.e. the plan itself is the
low speed. `lps='cruise'` (pure set-speed follow) accounts for <1%. **Not** SLC, not nav, not a
curve controller — all disabled (below).

**Secondary mechanism — engage-time set speed**: `IQE2ESetSpeedMode=1` (fixed-mode semantics) +
`IQE2ESetSpeedUseCurrent=True` → `VCruiseHelperIQ.get_iq_mode_initial_set_speed_kph` clips the
*initial* set speed at engagement to the current speed. So engaging at 30 mph and pressing Set
once can leave v_cruise at ~30; the driver must hold RES/+ to climb (LongIncrementsEnabled=False
→ +1 mph taps only). If the user "set 45" by tapping, verify the *HUD* set speed actually reads 45.

## (b) Code paths that can cap v_cruise below the set speed (3736edc)

| # | Path | Gate param(s) | Device value | Active? |
|---|---|---|---|---|
| 1 | e2e accel = model `desiredAcceleration`; cruise accel only via `get_e2e_accel` (≤0.5 m/s², τ15s) | `ExperimentalMode` (+ `expSpeedConv`) | **True** | **YES — dominant** |
| 2 | Initial set speed = current speed on engage | `IQE2ESetSpeedMode=1`, `IQE2ESetSpeedUseCurrent` | 1, **True** | **Yes at engage** |
| 3 | `update_targets`: `min(cruise, speedLimitAssist, nav)` → `output_v_target` | SLC needs `IQSpeedAssistMode==3` (mode 3 sets `speed_limit_controller=True`); nav needs `iqNavState.valid` | mode=**1** → SLC display-only; nav not engaged | No |
| 4 | `SLCSetSpeedToLimit` → writes v_cruise down to `speedLimitFinalLast` | `SLCSetSpeedToLimit` | False | No |
| 5 | `VisionCurveSpeedController` / `MapCurveSpeedController` | respective params | both False | No |
| 6 | `EnableSpeedLimitControl` → `carControl.cruiseControl.speedLimit` (car-side LFA cap) | `EnableSpeedLimitControl` | False | No |
| 7 | `EnableSLPredReactToCurves` / `EnableSLPredReactToSL` (predictive SLC) | params | both False | No |
| 8 | `_apply_force_stop` → v_target → 0 after 1 s model stop request | `IQForceStops`, `IQDynamicModelStopTime` | True, 3.5 s | Only near model-predicted stops |
| 9 | `controlsState.forceDecel` → `v_cruise=0` | driverMonitoring awareness < 0 (driver-attention) | — | alert-driven only |
| 10 | Non-e2e `get_cruise_accel`: `a_x_allowed` lateral-envelope clip + `allow_throttle` coast clip <2.5 m/s | (curve accel trade-off) | always | minor, non-e2e only |
| 11 | `cruise_envelope` next-speed-limit pre-slow | needs `controller_enabled` and `mode_assist` (mode 3) | off | No |
| 12 | `EnableCurvatureController` → `hudControl.curvatureControllerActive` (HUD flag only — **not a speed cap**) | `EnableCurvatureController` | True | display-only |

## Settings audit table

### Longitudinal / speed

| param | current | what it does | recommendation |
|---|---|---|---|
| `ExperimentalMode` | True | model-driven longitudinal (the speed cap source) | keep if user likes it; this is why it holds <set — consider lower expectations or toggle off to test pure ACC |
| `IQE2ESetSpeedMode` | 1 | e2e set-speed mode (fixed/current initial) | keep |
| `IQE2ESetSpeedUseCurrent` | True | initial set speed = current speed at engage | **likely the "set 45" confusion** — if user wants a fixed cruise, set False and use `IQE2ESetSpeedMph` |
| `IQE2ESetSpeedMph` | 65 | fixed initial set when UseCurrent=0 | set to preferred highway speed only if toggling above |
| `expSpeedConv` | True | allows ≤0.5 m/s² convergence toward set speed in e2e | keep True (off would be worse) |
| `AlphaLongitudinalEnabled` | True | openpilot controls gas/brake | keep |
| `LongitudinalPersonality` | 2 | cereal enum: aggressive=0, standard=1, **relaxed=2** — current value = Relaxed, the user's chosen mode | leave at 2 (relaxed) — is user's intended setting |
| `IQDriveProfile` | neutral | drive profile preset | fine |
| `IQDynamicMode` | False | conditional ACC↔blended switching (all IQDynamicConditional* sub-params configured but inert) | fine off; enabling changes longitudinal character — don't flip casually |
| `IQForceStops` / `IQDynamicModelStopTime` | True / 3.5 s | model-initiated stops behind lead | keep; raise stop-time only if stops feel premature |
| `IQCustomStopDistance` | 2 | e2e stop distance | fine |
| `IQE2EDistanceControl` | True | e2e distance controller enabled | keep |
| `IQGasOverrideBoost` | False | accel boost on gas press | enable (True) if user wants snappier gas-override response |
| `EnableLongComfortMode` | False | gentler accel profile | **candidate: enable for comfort** |
| `DisengageOnAccelerator` | False | gas doesn't disengage | keep (safer) |
| `AutoCruiseControl` / `AutoEngage` | 0 / 0 | auto ACC resume / auto-engage | fine off |
| `LongIncrementsEnabled` | False | ±5 mph on long-press; currently only +1 taps → slow to reach 45 from low engage | **recommend True** so set-speed changes are fast (HoldStep=5 already set) |
| `newLeadMpc` | True | newer lead MPC | keep |
| `StandstillTimer` | False | — | fine |

### Speed-limit control (all display-only today)

| param | current | note |
|---|---|---|
| `IQSpeedAssistMode` | 1 | 0=off, 1=show only, 3=enforce — **this is why ShowSpeedLimits=True but no limiting** |
| `ShowSpeedLimits` | True | HUD limit display |
| `SpeedLimitController` / `MapCurveSpeedController` / `VisionCurveSpeedController` / `SLCSetSpeedToLimit` / `EnableSpeedLimitControl` | all False | no speed-limit or curve-speed limiting anywhere — **confirmed none is capping speed** |
| `SLCPolicy` / offsets / fallbacks | 1 / +2,0 / prev-limit | inert while mode=1 |
| `MapCurveSLCOffset` | False | inert |

### Lateral / steering smoothness

| param | current | what it does | recommendation |
|---|---|---|---|
| `CameraOffset` | 0.0 | camera-warp offset of model input (see lane-offset study: ~10 cm right-of-centre stance on v4 drive) | hold; only trial ±0.02 after v5-drive bias check |
| `IQHkgReducedTorqueFeedback` | True | ×0.8 kp (our tune baseline) | keep (all tuning assumes it) |
| `IQLatJerkGain` | 1.0 | lateral jerk smoothing gain | could try <1 for softer entries — untested |
| `IQLateralAccelSlew` | True | lataccel slew limiter | keep |
| `IQLateralCurvatureLookahead` | False | extra curvature lookahead | leave off |
| `LatSmoothSec` | 13 | (path smoothing window param — large value) | leave; unverified semantics |
| `ModelLatSmoothSec` / `ModelSmoothingEnabled` | 0 / False | model path smoothing | fine |
| `EnableSmoothSteer` | False | smooth-steer feature | leave off |
| `LaneChangeNeedTorque` | 0 | lane change needs nudge | fine |
| `LaneChangeDelay` / `IQLaneChangeTimer` | 0 / 0 | no lane-change delay | fine |
| `LaneChangeBsd` | 0 | BSM blocks lane change — off | consider enabling if desired |
| `IQBlinkerMinLateralSpeed` | 20 | min speed (unit ambiguous) for blinker-lane-change | fine |
| `NavExitLaneChange` / `IQLaneTurnDesire` | True / False | nav exit lane changes on; turn-signal lane turns off | fine |

### UI/alerts

`ShowSpeedLimits=True`, `ShowRoadName=True`, `IQRoadNameOverlay=True`, `IQExpandedStatus=True`,
`IQBlindSpotAlerts=True`, `IQBlinkerIndicators=True`, `IQAlertSilence=False`, `OnroadScreenOffTimer=15`,
`EnableCornerRadar=0`, `IsLdwsCar=0`, `LaneLineCheck=0` — all cosmetic/informational; nothing
drive-relevant to change.

### Model bundle

`ModelManager_ActiveBundle` = NNMV2 (index 35, "North Nevada Model V2"), `ModelRunnerTypeCache=1`,
`IQEmacEnabled=False`, `IQEmacSmallModel=False`. NNMV2's low-speed road-speed choices are the e2e
cap — a different bundle would change it, not a param.

## Bottom line

1. **The cap is the e2e model, not a limiter**: ExperimentalMode → `lps=e2e` in ~99–100% of
   below-set cruising frames; the model's own speed plan sits below `hud_v` while every SLC/nav/
   curve limiter is disabled. Fix = accept it (NNMV2 chooses road-appropriate speeds), disable
   ExperimentalMode for ACC-style follow, or try a different model bundle.
2. If "won't climb" happens right after engage, `IQE2ESetSpeedUseCurrent=True` pins the initial
   set speed to current speed — combined with `LongIncrementsEnabled=False` (+1 mph taps) it takes
   many presses to reach 45. Recommend `LongIncrementsEnabled=True` (5-mph holds) regardless.
3. Nothing else caps speed: `SpeedLimitController`, `MapCurveSpeedController`,
   `VisionCurveSpeedController`, `SLCSetSpeedToLimit`, `EnableSpeedLimitControl`, predictive SLC —
   all False; `EnableCurvatureController` is a HUD flag only.

## Round 2 — remaining feel-relevant params (post Round-1; verified consumed on the Hyundai path)

Candidates not yet changed, screened for actual consumption in 3736edc code.

### Worth considering

| param | now | code effect (verified) | recommend |
|---|---|---|---|
| `LongitudinalPersonality` | 2 (**relaxed** — enum was misread: cereal is aggressive=0, standard=1, relaxed=2) | `long_mpc.py` `get_T_FOLLOW`: aggressive=1.25 / standard=1.45 / **relaxed=1.75 s**; `get_jerk_factor`: 0.5/1.0/1.0 — relaxed = longest gap, gentlest lead tracking | **leave at 2 (relaxed)** — the earlier "set 1 (standard)" recommendation was based on the reversed enum and is withdrawn |
| `IQGasOverrideBoost` | False | `longitudinal_planner.py` AccelBoost: gas held >10 mph ramps accel up to +1.0 m/s², held till disengage, bleeds <10 mph (verified consumer, UI-described) | **keep off for now** — 12 gas overrides/drive suggests user already overrides plenty; boosting makes overrides stronger but riskier; revisit if user says overrides feel weak |
| `IQLatJerkGain` | 1.0 | `latcontrol_torque.py:290` — scales the jerk-lookahead damping term (`jerk_ahead = LP × _jerk_gain`) | keep 1.0; <1 reduces damping ahead of curves — only touch if entries feel harsh *after* v5 data (a real knob, unlike LongComfortMode) |
| `LaneChangeBsd` | 0 | consumed in compiled IQ components (iqlocd) — BSM veto of lane changes | **recommend 1** — blind-spot block on auto lane change is a safety win at zero smoothness cost |
| `IQCustomStopDistance` | 2 | `custom_stop_distance.py` — **only reached via `apply_e2e_stop_distance` → e2e only** | inert now that ExperimentalMode=False; leave |
| `IQDynamicModelStopTime` | 3.5 | `iq_dynamic` force-stop ramp — force_stop only fires through IQDynamic path (IQDynamicMode=False → conditional-off → likely inert; keep in mind if dynamic mode ever enabled) | leave |

### Keep as-is (verified live but no reason to change)

| param | now | why keep |
|---|---|---|
| `IQHkgReducedTorqueFeedback` | True | ×0.8 kp + friction_scale 0.7 — entire v3/H1/v4/v5 tune calibrated on it |
| `IQLateralAccelSlew` | True | `LateralAccelerationSlewLimiter` — the 3.0 slew cap that also bounds exit unwind; keep |
| `IQLateralCurvatureLookahead` | False | consumed in controlsd (curvature lookahead into desired path); we already run D1 lookahead — don't stack |
| `LatSmoothSec` | 13 | iqmodeld → ×0.01 = **0.13 s** path smoothing (real); `ModelLatSmoothSec`=0 off — fine |
| `DisengageOnAccelerator` | False | selfdrived.py — gas override keeps engagement; **keep False** (safer; user overrides gas often) |
| `CameraOffset` | 0.0 | leave per lane-bias decision (re-measure on next drive first) |
| `AutoCruiseControl` / `AutoEngage` / `iqMqbAccResume` | 0/0/False | binary-consumed ACC-resume/auto-engage behaviors — fine off for a commute car |
| `IQAlertSilence` | False | UI/sound; keep audible alerts |

### Verified no-ops on this car (don't bother)

- `EnableSmoothSteer` (False): `controlsd` gates it on `is_curvature_car` (steerControlType==curvature) — Tucson is torque-type → dead. Same class as LongComfortMode.
- `EnableLongComfortMode` (now True): no consumer on Hyundai path (Round-1 finding stands).
- `IQCustomStopDistance`, `IQDynamicModelStopTime`: gated behind e2e/dynamic paths that are now off.

### Round-2 top picks (if the user wants one more change before the drive)

1. ~~`LongitudinalPersonality` 2 → 1~~ — **withdrawn**: enum was reversed; value 2 is *relaxed* (T_FOLLOW 1.75 s, the gentlest profile) and is the user's intended UI selection. Leave at 2.
2. **`LaneChangeBsd` 0 → 1** — free safety.
3. Everything else: keep — the meaningful knobs are either already set (Round-1) or gated/no-op on this car.
