# Drive set v6 (routes 0x36–0x3b, 59 segments, 2026-10-01) — grade, engagement failure, dash warnings, button mapping

Read-only analysis. Nothing installed. Sources: `hourly/reports/20261001T203456Z.md`, `export-v3b/`, on-device
read-only extractor `extract_engage.py` (pandaStates / carState / buttonEvents / selfdriveState / onroadEvents / alerts).

## 1. Drive grade

Steering (engaged, unpressed) vs. pre-fix baseline: band RMS 6.69 → 5.46, saturation 0.038 → 0.016, lane-change
handback median 0.235 → 0.160, steer-fault frames 1847 → 43 (0 permanent). One low-speed (~6.3 m/s, ~1 Hz) wobble
candidate in 0x38-11 — the known parking-lot family, not the highway one. No steering-related alerts.

Longitudinal: launch command peaks stay capped (L1c). Stops: 20, 18 behind a lead; final-stop nod median −0.10 m/s²
(S1 holding). Set-speed gap median 0.08 m/s (C1/Experimental-off holding). A3 (highway catch-up): only 9 climb
windows, median 9.4 s, 16 % saturation — not enough valid highway data to grade; neutral so far.

Housekeeping: active model changed KARNBIRRLV2(77) → MICHAELRLV2(75) during this set (not by me). Personality param
is still 2 (Relaxed) but "Driving Personality: Standard" popped 3× in 0x38-13 — the distance/gap button cycles
personality in this fork; it was back on Relaxed by end of drive.

## 2. "Only stock ACC engaged, comma stayed out until I restarted the car"

Timeline from device logs (UTC):
- 19:41:48 route 0x38 ends: car parked, ignition line off (normal shutdown). Comma had been fine (engaged most of 0x38).
- 19:49:50 route 0x39-0 begins **with the car already moving at 18.5 m/s and stock ACC already engaged** (TCS ACC_REQ=1 at
  comma t=1.3 s, before the panda had any safety mode). Comma was off/booting during the car restart and the first
  minutes of the drive — matches "I restarted the comma".
- 7.7 s: panda switches elm327 → hyundaiCanfd/44 (handoff happened), stock ACC drops out (panda now blocks camera SCC).
- 7.7 s → 100 s: `cruiseState.available` stays 0 for the rest of the route, no SET/RES/MAIN button events recorded,
  controlsAllowed stays false. Route ends 19:51:30 with ignition off (car shut down).
- 19:51:35 route 0x3a-0: fresh boot with car in Park → ready at 18.9 s, SET release engages comma normally.

Reading: not the tune and not the panda. The comma booted *into* a moving car whose stock ACC was already active.
The startup arming sync (arming fix) requires a clean, fresh SET/RES release after it advertises ready; none is
recorded in that 100 s window, so it is not possible to tell from logs whether a press was made and rejected or
not made. Hypothesis to test (supervised, safe): start the comma after the car is already moving with stock ACC on, then
press SET once and see if it arms. If it does not, the arming fix's "fresh release" path needs a mid-drive boot case.

Also seen (same family, different cause): **pressing the MAIN (car+speedo) button while the comma is on turns the
comma off.** Three times in this set (0x3a-1 @47.8 s, 0x3b-1 @46.5 s, 0x3b-2 @39.4 s) `available` dropped 1 → 0 on a
MAIN release and the comma stayed unavailable until a later SET release (0x3b-6). Both the app (`main_enabled` toggle,
carstate.py ~L1033) and the panda (`acc_main_on` toggle → AOL lateral exit on falling edge) treat MAIN as a toggle.

The 2 `accFaulted` frames + "Cruise Fault: Restart the car" in 0x3b-16 occur at 30.9 s exactly as the ignition line
goes off — power-down artifact, not a fault during driving.

## 3. Dash "lane assist" / "speed limit" messages

Unchanged from the raw-CAN finding (research/lanechange-lfa §2): the camera's own 2.0 s periodic self-check flips
LFA 0x12a (LKA_MODE 1→7, FCA_SYSWARN) and requests cluster popup `HDA_InfoPUDis=3`; IQ forwards it. Zero correlation
with MDPS faults, IQ state, speed, or torque. The speed-limit message is the same message family (cluster/ADAS
forwarding from the camera when IQ owns longitudinal) — inferred, not separately decoded yet. Neither is caused by
the tuning; a fix is forwarding-side (what IQ sends in 0x12a/0x1e0 vs the camera's own values) — the LFA-AB package
holds the candidate variants, untested on-car beyond variant 0.

## 4. Requested button mapping — what is possible without touching panda safety

- **Steering-wheel (LFA) button → steering only**: already works. 43,410 frames (~7 min) of lateral-only control in this
  set, toggled by the LFA button via the fork's always-on-lateral path, as long as comma MAIN is on.
- **SET button → gas/brake + steering at current speed**: already works (C1).
- **MAIN (car+speedo) button → engage gas/brake + steering**: *not possible in software only.* Panda firmware grants
  longitudinal `controls_allowed` solely on a SET/RES *release* (hyundai_common.h) and treats MAIN as an on/off toggle;
  the app cannot send a SET button itself (tx hook blocks it). Making MAIN engage requires a panda safety-code change.
- **Achievable software-only fix**: stop MAIN from turning the comma off — on this Tucson, ignore the MAIN release
  toggle in carstate (keep `main_enabled`), so a MAIN press costs at most the steering-only session (panda drops
  lateral on the MAIN falling edge, re-granted on the next SET release or next MAIN press). Not built; awaiting choice.
