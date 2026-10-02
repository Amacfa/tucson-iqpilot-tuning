# Tucson comma/IQ.Pilot tuning record

Offline analysis and reversible install packages for a **2024 Hyundai Tucson (4th gen,
camera-SCC, CAN-FD)** running comma/IQ.Pilot, currently at release
`3736edcade7fe93229ee7e8fcf38d77608db31be`. Every change below was fitted offline from
this car's own drive logs, simulated before install, installed only while parked, and is
reversible with the package's `manage.py --rollback`. Native Hyundai and panda safety
limits (torque 270, rate 2 up / 3 down, accel limits) are unchanged throughout.

## What we built on

Teal's fixes for the camera-SCC configuration: the dedicated steering-message path
(active steering damping fields + camera-side steering/touch feedback), the forwarding
correction that stopped stock and modified camera-feedback messages producing duplicate
counter sequences, and the *Reduce Steering Feedback* option (P gains x0.8, friction
compensation x0.7). That removed the large highway oscillation. Everything below sits on
top of it.

## Installed fixes — what, why, result

All items are code changes (not app settings) unless marked. Each links to the
package (manifest, forward/reverse patch, hashes) and the evidence that motivated it.

### Lateral — steering

| fix | what changed | why (what the logs showed) | result |
|---|---|---|---|
| **v5 table** ([package](research/tune-v5-table/package), [fit](research/tune-v3-table/LAT_GAIN_FIT.md), [drive](research/drive-v5)) | `latcontrol_torque.py`: speed-indexed `latAccelFactor` for `HYUNDAI_TUCSON_4TH_GEN` — `[8,12,15,25] m/s -> [2.95,3.45,4.05,4.05]` instead of one scalar | measured torque->lat-accel gain is strongly speed dependent on this car; the single scalar over-turned in 25–35 mph curves (tracking ratio ~1.15) and under-turned at highway speed | curve over-turn 1.15 -> ~1.0–1.1; 0 wobble episodes over the last 5 drives |
| **v4 low-speed P** ([package](research/tune-v4-lowspeed-kp/package), [drive](research/drive-v4)) | P scale 0.7 below 13 m/s (blending to 0.6 at 17 m/s) | the residual sub-1 Hz "twitch" at town speeds was P-term driven (corrections larger than the error warranted) | town-speed twitch gone; no felt wobble |
| **H1 hand-back** ([package](research/tune-H1-handback/package), [report](research/lanechange-lfa/LANECHANGE_LFA_REPORT.md)) | P x0.6 above ~15 m/s; 0.3 s first-order low-pass on the friction-compensation error input | after lane changes / driver hand-back the friction term reacted to measurement quantisation, producing a 2–3 cycle wiggle (16 % of hand-backs on baseline) | clean lane-change exits |
| **D1 delay** ([package](research/tune-D1-delay/package), [analysis](research/lateral-pass2)) | `controlsd.py`: cap this fingerprint's request-buffer lookahead at 0.15 s while `lateralDelay` is unestimated (was fixed 0.30 s) | measured command->response delay on this car is ~0.15 s; the 0.30 s lookahead over-anticipated curve exits | less curve-exit overshoot |
| **LFA-AB variant 0** ([plan](research/lfa-ab/LFA_AB_PLAN.md), [results](research/lfa-ab/RESULTS.md)) | `hyundaicanfd.py`: LFA 0x12a field variant selected after A/B of stock-vs-IQ field values | to locate the source of the dash "Check LFA" warning | variant 0 kept; warnings attributed to startup message gap (below) |

Settings on the lateral side: `LaneChangeBsd=1` (blind-spot veto on auto lane change).

### Longitudinal — gas / brake

| fix | what changed | why | result |
|---|---|---|---|
| **Experimental Mode off** (setting, [audit](research/settings-audit)) | plan source `cruise` instead of `e2e` | the e2e planner sat below the set speed 33 % of cruise time ("won't climb to set speed") | time capped under target 33 % -> 2 %; set-speed error ~0 |
| **L1c launch jerk cap** ([package](research/long-L1c/package), [evidence](research/long-L1c/LAUNCH_EVIDENCE.md)) | `hyundai/carcontroller.py`: cap `jerk_u` ramp during the first seconds after a stop | launches stepped straight to the accel ceiling (peaks ~3.0 m/s^2) — felt as a lurch | launch peak <= 2.0 m/s^2, capped as designed |
| **C1 SET re-engage** ([package](research/setspeed-C1/package), [report](research/setspeed-C1/SETSPEED_C1_REPORT.md)) | `cruise.py`: SET adopts current speed on re-engage; RES still recalls the old set speed | after a manual slow-down, SET chased the old (higher) target or braked to a stale lower one | 25/25 engages adopted actual speed |
| **S1 stop taper** ([package](research/stop-taper-S1/package), [report](research/stop-taper-S1/S1_REPORT.md), [drives](research/drive-s1b)) | `smooth_stops.py`: `SETTLE_DECEL 0.8 -> 1.0`, `TAPER_SPEED 1.0 -> 0.6` | in 24/28 stops the requested gentle brake under ~2 mph was only a third delivered by the car, giving a 4+ s creep and a final nod | final nod -0.54 -> -0.33 m/s^2 (~40 % less); crawl ~1 s shorter |
| **A3 cruise accel ceiling** ([report](research/cruise-accel-A3/A3_REPORT.md), [install](research/cruise-accel-A3/INSTALLED.md)) | `longitudinal_planner.py`: `A_CRUISE_MAX_VALS` 0.8 -> 1.0 at the 25 m/s breakpoint | 9.6 % of 15–25 m/s cruise frames sat on the accel ceiling; ~4 s to close a highway gap | installed, awaiting first drive |
| **L2 launch hold cap** ([package](candidates/launch-L2/package), [log](candidates/INSTALL_LOG.md), [evidence](research/launch-stop-v7)) | `hyundai/carcontroller.py`: cap the accel request at 1.0 m/s^2 while the car is still at standstill; normal ramp resumes once rolling | brake-release launches commanded ~2.0 but the car peaked 2.6–3.8 m/s^2 — the harshest longitudinal event in the logs; predicted peaks ~2.0–2.3 | installed 2026-10-02, physical check pending |
| **S2 stopped-lead gap** ([package](candidates/stopdist-S2/package), [log](candidates/INSTALL_LOG.md), [evidence](research/launch-stop-v7)) | `long_mpc.py`: `STOP_DISTANCE` 3.0 -> 4.0 m (also +1 m following margin at speed, small vs t_follow·v) | measured stopped-lead gaps 1.8–3.0 m — tighter than the 3.0 constant implies | installed 2026-10-02, physical check pending |

Settings on the longitudinal side: `LongIncrementsEnabled=True` (hold = +-5 mph);
`LongitudinalPersonality=2` (Relaxed, user's choice — note enum is aggressive=0 /
standard=1 / relaxed=2). `EnableLongComfortMode` and `IQGasOverrideBoost` are no-ops on
this car (Tesla/VW-only and e2e-only respectively) — see [settings audit](research/settings-audit).

### Platform — not settings, not tuning

| fix | what | why |
|---|---|---|
| **Arming / warning repair** ([package](candidates/arming), [log](candidates/INSTALL_LOG.md)) | `carstate.py` / `card.py` / `behavior.py` / `pandad.cc`: SET/brake permission ordering, MAIN-off command tail, startup ownership before replacement LFA messages exist | reproduced 54/54 rejected commands and the startup LFA gap in isolated replay; caused "won't engage" + LFA warnings |
| **P1 personality button** ([package](candidates/personality-P1/package), [log](candidates/INSTALL_LOG.md)) | `selfdrived.py`: the gap/personality button write is now a blocking put, so the background param re-read can't snap it back | every press decremented from the stale value — it always showed Aggressive; now it cycles Standard -> Aggressive -> Relaxed -> Standard; installed 2026-10-02, physical check pending |
| **M1 MAIN-button no-disarm** ([package](candidates/mainbtn-M1), [log](candidates/INSTALL_LOG.md)) | `carstate.py` / `behavior.py`: pressing MAIN while the comma is on no longer toggles `main_enabled` off; app ends its lateral session (panda drops lateral on the MAIN falling edge), long keeps running; SET/RES arming and panda safety unchanged | 3 MAIN presses in the v6 drives turned the comma off and nothing engaged until SET; installed 2026-10-01, physical check pending |
| **Fingerprint** ([report](candidates/fingerprint/REPORT.md)) — **built, NOT installed** | FW table entry (adds the 99211-CW020 camera FW under `HYUNDAI_TUCSON_4TH_GEN`) so the Tucson can auto-identify | today the platform is forced by the manual `CarPlatformBundle` pick (no FW query; `carFw` empty on every recent drive); the fix only matters if that pick is cleared. Install needs: apply parked, clear the manual pick, one ignition cycle to confirm `fingerprintSource=fw` |

## Upstream PRs (Teal IQ.Pilot, base release-candidate @ 9007895, from fork rozal/IQ.Pilot)

Eight PRs opened on https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot — see
[upstream/UPSTREAM_PRS.md](upstream/UPSTREAM_PRS.md) for the table, PR bodies
and the opener script. The LFA-AB hyundaicanfd variant switch was excluded
(variant 0 is byte-identical to unpatched).

| PR | branch | local commit |
|---|---|---|
| [#23](https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/23) | fix/personality-button-blocking-put | `895fde1` |
| [#24](https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/24) | hyundai/tucson-4th-gen-fw-cw020 | `4991462` |
| [#25](https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/25) | hyundai/tucson-canfd-startup-arming | `250398a` |
| [#26](https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/26) | hyundai/tucson-main-button-keeps-long (stacked on #25) | `4bfdacc` |
| [#27](https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/27) | cruise/set-adopts-current-speed | `4934b28` |
| [#28](https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/28) | hyundai/tucson-canfd-launch-smoothing | `1026647` |
| [#29](https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/29) | hyundai/tucson-lateral-tune | `e6254fd` |
| [#30](https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/30) | long/stop-and-cruise-tuning | `088a1f6` |

## Still open / watching

- A3 first-drive evaluation.
- Lane position ~4 in left of centre under the KarnbirrLV2 model (was centred on the previous model) — camera-offset nudge or model change if it bothers the driver ([model eval](research/model-eval), [lane offset](research/lane-offset)).
- One self-clearing `accFaulted` event — watching for repeats.
- Boot: CAN settle takes 10–30 s; engaging before the UI says ready gives a transient fault.

## Layout

- `reports/` — drive-log analysis reports (`REPORT.md`, `DEEP_RESEARCH.md`) and the
  arming-package README/BUILD_NOTES.
- `scripts/` — analysis and export scripts used to build the frame dataset
  (`export_drive_summary.py`, `analyze_*.py`, `build_long.py`) and the route23
  isolated replay tooling under `scripts/route23/`.
- `candidates/arming/` — guarded install package (manifest, manage.py, forward/reverse
  patches) for the arming/warning repair at 0b8c190c. `software_validation_passed`
  is false pending the isolated route23 runtime replay.
- `candidates/tune/` — guarded install package for the steering/longitudinal tune
  (speed-scheduled latAccelFactor + measurement low-pass, CAN-FD jerk_u floor/boost,
  friction 0.108745 -> 0.12). Must be applied after the arming package.
- `candidates/fingerprint/` — the CW020 camera fingerprint candidate patch and its
  notes (patch/diff and report only).

## Safety notes

- `manage.py` in each candidate package defaults to read-only `--check`; `--apply`
  refuses while `software_validation_passed` is false and requires a parked,
  ignition-off device with exact version and parameter pins.
- Sensitive data (route IDs, dongle IDs, IPs, keys, params dumps) has been stripped
  or redacted; binary exports (.npy/.jsonl.gz/rlog) are intentionally not included.
