# PR descriptions — IQ.Pilot (target: release-candidate)

Eight branches, one commit each, based on `origin/release-candidate` @ `90078952`.
Evidence repo: https://github.com/Amacfa/tucson-iqpilot-tuning (analysis + drive data).

---

## 1. fix/personality-button-blocking-put

**selfdrived: write personality param synchronously**

The personality button wrote `LongitudinalPersonality` with `put_nonblocking`
while `params_thread` re-reads it every 100 ms — the async write landed after
the thread's stale read, so the value snapped back (logged aggressive at +0 ms,
standard again at +67 ms) and every press showed "Aggressive". One-line change
to `put`, the same blocking call the longitudinal-settings path already uses.
Affects all cars.

## 2. hyundai/tucson-4th-gen-fw-cw020

**hyundai: add Tucson 4th-gen fwdCamera CW020 firmware**

US-market 2024 Tucson with fwdCamera FW string `99211-CW020 14Z` does not
fingerprint. Adds that camera firmware version to the
`HYUNDAI_TUCSON_4TH_GEN` fingerprint DB entry. Affects
HYUNDAI_TUCSON_4TH_GEN only; other cars unchanged.

## 3. hyundai/tucson-canfd-startup-arming

**hyundai: add Tucson CAN-FD startup arming and handoff**

On startup the Tucson CAN-FD camera-SCC stack races ownership handoff:
replacement LFA packets must stay inactive until panda confirms the new
safety mode, and SET/RES release must complete arming. carstate adds the
arming/handoff state machine, card.py adds `_sync_startup_arming` and the
pending-handoff paths, pandad.cc publishes health after
`configureSafetyMode`. Affects HYUNDAI_TUCSON_4TH_GEN only; unlisted cars
take the previous code paths verbatim. 54/54 rejected commands reproduced
in isolated replay.

## 4. hyundai/tucson-main-button-keeps-long

**hyundai: keep longitudinal control on Tucson MAIN press** (stacked on PR 3 — <PR_3_LINK>)

A MAIN press latched `main_enabled` off and disarmed the stack, though
panda only drops lateral permission on the MAIN falling edge —
longitudinal `controls_allowed` is untouched. carstate skips the
off-direction of the MAIN-release toggle under the release gate (MAIN
still turns main ON when off); behavior emits `alcDisengaged` without
`kill_all` and never engages lateral from MAIN (the app cannot know
panda's `acc_main_on` parity). Driver-facing: MAIN while on ends the
steering session, gas/brake keep going; steering returns on SET release.
Logged: 3 MAIN releases dropped `cruiseState.available` 1→0 mid-drive.
Affects HYUNDAI_TUCSON_4TH_GEN only.

## 5. cruise/set-adopts-current-speed

**cruise: adopt current speed on SET re-engage**

On re-engage a SET/decel press kept the stale stored target instead of
adopting current speed. Matches upstream openpilot `initialize_v_cruise`
semantics: SET clips to current speed, RES recalls `v_cruise_kph_last`.
Ported onto the `volkswagen_standby_set_speed` path unchanged. Not
car-gated — affects every non-pcmCruise car, as upstream does. Measured:
25/25 engages adopted actual speed on device.

## 6. hyundai/tucson-canfd-launch-smoothing

**hyundai: bound Tucson CAN-FD launch accel and jerk_u**

A brake-held launch on the Tucson CAN-FD releases with the full 2.0 m/s²
request and an unbounded `jerk_u`. Two hunks, both gated on
`CAR.HYUNDAI_TUCSON_4TH_GEN` — other Hyundai CAN-FD cars are byte-identical:
cap accel at 1.0 while `standstill`; bound `jerk_u` against the raw accel
request (interp cap on vEgo [3,8]→[1.2, jerk_max_u]) instead of jerk alone.
Measured: launches released at 2.0 peaked 2.6–3.8 m/s² (9 episodes);
released at 1.28–1.65 peaked 1.8–2.5 (6 episodes).

## 7. hyundai/tucson-lateral-tune

**hyundai: add per-car Tucson lateral tune**

The Tucson under-responds at low speed and wobbles on curve exits with the
stock torque tune. Per-car `LAT_TUNE_PER_CAR` dict keyed on `carFingerprint`;
unlisted cars take the exact pre-patch path (kp unchanged, raw error to
`get_friction`, no delay cap, static `latAccelFactor`): friction
0.108745→0.12 (params.toml row), speed-scheduled latAccelFactor
[8,12,15,25]→[2.95,3.45,4.05,4.05], kp_scale [13,17]→[0.7,0.6] on the P
table, 0.3 s LP on the friction-error input, and controlsd caps the
lateralDelay lookahead at 0.15 s while lagd is `unestimated` (gated on
table membership). Measured: curve-exit tracking ratio 1.28–1.82 → ~1.0;
in-turn wobble episodes eliminated.

## 8. long/stop-and-cruise-tuning

**long: tune stop settle, stop distance, cruise accel**

Preference tuning — global knobs, affects all cars. `SETTLE_DECEL`
0.80→1.00, `TAPER_SPEED` 1.0→0.6 (firmer settle, shorter taper);
`STOP_DISTANCE` 3.0→4.0 (+1 m stopped-lead gap, also +1 m following
distance, small vs `t_follow·v`); `A_CRUISE_MAX_VALS` 0.8→1.0 at the
25 m/s breakpoint (≤ ACCEL_MAX 2.0). Measured: median final nod
−0.54→−0.33 m/s²; 9.6% of 15–25 m/s frames sat at the 0.8 ceiling.

---

**Excluded**: hyundaicanfd.py LFA-AB variant switch — variant 0 is
byte-identical to unpatched, nothing to merge.
