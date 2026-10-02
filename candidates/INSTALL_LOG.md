# INSTALL_LOG — device install of both 457ea8e packages

Device HEAD: `457ea8e2d33eb3f48f5805b35e6dff9a046c312c`. Installs run on the comma
from `/data/tucson_stage/` with the device venv python.

## Timeline

- **2026-09-24 07:39:42Z** — arming package `--apply`
  (backup `/data/iq-warning-backups/20260924T073942.872889Z-apply`)
- **2026-09-24 07:40:05Z** — tune package `--apply`
  (backup `/data/iq-warning-backups/20260924T074005.858580Z-apply`)
- Reboot after both applies.
- **Correction (added 2026-10-02):** the following packages were also applied and are
  live on device — C1 (cruise.py `1abb8a1e`) applied 2026-09-30T20:43Z, S1
  (smooth_stops.py `9da88dc0`) applied 2026-09-30T22:13Z, A3
  (longitudinal_planner.py `d6abce2e`) applied 2026-10-01T06:18Z. Earlier notes calling
  C1 "not installed" were wrong.

## Post-reboot verification

- All 9 source files hash-verified at candidate values via `sha256sum -c`.
- Running `/proc/<pandad>/exe` sha256 = `86aaa982fa36f61a3a5eee79190a6814194960a5fe5b6881035b5a5c15863106`
  — matches neither manifest baseline nor candidate, **expected**: IQ's boot path
  (`iqpilot/system/manager/build.py`, scons, MD5 decider, `/data/scons_cache`)
  recompiled pandad from the installed candidate `pandad.cc`. `objdump -d -C`
  confirms candidate semantics: `bl configureSafetyMode` at 0x638f0 precedes
  `bl process_panda_state` at 0x63914 (baseline has them reversed). Conclusion:
  the pandad *binary* hash is not a stable verification target; candidate
  pandad.cc source hash + call-order check is.
- Boot log clean: 0 error/fault/traceback lines in swaglog after reboot.

## Tool defects found and fixed

1. **tune `manage.py --verify-installed` crashed** with StopIteration at the
   pandad-executable check (inherited from the arming manager; tune ships no
   binary). Fix: pandad check removed; verify now checks the 3 files at
   candidate hashes + HEAD. → PASS.
2. **arming `manage.py --verify-installed` refused** on
   `validation_dependencies[.venv/.../carcontroller.py]` and on the torque
   controller hash — both legitimately changed by the tune package applied
   afterward. Fix: when `installed=True`, both checks accept the baseline hash
   or the tune candidate hash (read from a sibling `tune-*/package/manifest.json`
   when present, else a hardcoded fallback).
3. **arming `--verify-installed` pandad check replaced**: the exact
   `/proc/pid/exe` hash check now requires pandad.cc at the candidate source
   hash AND the running executable to show the candidate call order
   (`configureSafetyMode` before `process_panda_state` in the main loop).
   `checked_files` no longer refuses on the pandad binary's current bytes (boot
   rebuilds it from pandad.cc anyway); rollback still restores the backed-up
   binary.

## verify-installed outputs (post-fix, device)

```
$ cd /data/tucson_stage/arming-457ea8e/package && PYTHONPATH=/data/openpilot/.venv/lib/python3.12/site-packages:/data/openpilot /data/openpilot/.venv/bin/python manage.py --verify-installed
{"installed_and_running_verified": true, "changes_made": false, "physical_test_pending": true, "pandad_verified_by": "candidate source hash + disassembled call order"}

$ cd /data/tucson_stage/tune-457ea8e/package && PYTHONPATH=/data/openpilot/.venv/lib/python3.12/site-packages:/data/openpilot /data/openpilot/.venv/bin/python manage.py --verify-installed
{"installed_and_running_verified": true, "changes_made": false, "physical_test_pending": true}
```

## Test outputs (local, post-fix)

```
arming: {"apply_rollback_exact": true, "partial_write_failure_restores_originals": true, "temporary_files_removed": true, "unrelated_edit_refused": true, "mixed_original_candidate_rollback": true, "receipt_failure_restores_originals": true, "guards_survive_python_optimization": true, "pandad_call_order_check": true}
tune:   {"apply_rollback_exact": true, "partial_write_failure_restores_originals": true, "temporary_files_removed": true, "unrelated_edit_refused": true, "mixed_original_candidate_rollback": true, "receipt_failure_restores_originals": true, "guards_survive_python_optimization": true}
```

Physical A/B drive remains pending (`physical_validation_pending`).

## Fingerprint package (CW020, 457ea8e)

- 2026-09-24: built `tucson-fingerprint-457ea8e/package` (adds `99211-CW020` fwdCamera FW under `HYUNDAI_TUCSON_4TH_GEN`; in stock 457ea8e it exists only under `HYUNDAI_SANTA_CRUZ_1ST_GEN`). Baseline fingerprints.py verified byte-identical on device (`dd31c382`, both paths). Local tests: artifacts hashes + patch roundtrip + py_compile all true; manage guards all true.
- Staged at `/data/tucson_stage/fingerprint-457ea8e/package/`; `--check` → `{"check_passed": true, "changes_made": false, "head": "457ea8e2d33eb3f48f5805b35e6dff9a046c312c"}`. **NOT applied** — readiness `check_only`; physical parked fingerprintSource="fw" check pending.

## M1 MAIN-button no-disarm (3736edc)

- 2026-10-01: built `tucson-mainbtn-3736edc-M1/package` (behavior.py: guarded Tucson MAIN press -> `alcDisengaged` only, never `alcEngaged`, no kill_all; carstate.py both paths: MAIN release no longer toggles `main_enabled` off when the Tucson release gate is active, MAIN-press latch removed; SET/RES arming unchanged; panda safety unchanged). Local tests: `validation/test_m1.py` all true; artifacts hashes + patch roundtrip + py_compile true; manage guards 7/7.
- Staged at `/data/tucson-packages/M1/package/`; `--check` -> `{"check_passed": true, "changes_made": false, "head": "3736edc..."}`.
- **Applied** (user-approved) -> `{"completed": "apply", "backup": "/data/iq-warning-backups/20261001T222228.073696Z-apply", "services_restarted": false}`; `--verify-installed` -> `{"installed_and_running_verified": true, "physical_test_pending": true}`. On-device hashes: behavior.py `6c19eded9810`, carstate.py `ab334ec36480` (both paths). Physical check pending: MAIN press while engaged must leave long running + cruiseState.available true; next SET re-engages lateral.

## L2 launch standstill cap (3736edc)

- 2026-10-02: built `tucson-launch-3736edc-L2/package` (`.venv/.../iqdbc/car/hyundai/carcontroller.py`: `LAUNCH_HOLD_ACCEL_MAX = 1.0` caps the accel request while `CS.out.standstill`; base = installed L1c `d3915221`). Local tests: `validation/test_l2.py` all true; artifacts hashes + patch roundtrip + py_compile true; manage guards 7/7.
- **Applied** (user-approved, "Yes, install both") at 2026-10-02T03:16Z -> `{"completed": "apply", "backup": "/data/iq-warning-backups/20261002T031622.006662Z-apply", "services_restarted": false}`; `--verify-installed` passed. On-device hash: `5a03012c216cc0ef7e02593e970b5cf7c856b2f0e08b221d662b03fafd419af6`. Physical check pending: brake-release launches should peak ~2.0-2.3 m/s^2 vs the measured 2.6-3.8.

## S2 stopped-lead distance (3736edc)

- 2026-10-02: built `tucson-stopdist-3736edc-S2/package` (`iqpilot/selfdrive/controls/lib/longitudinal_mpc_lib/long_mpc.py`: `STOP_DISTANCE 3.0 -> 4.0`; base stock `2b6c5057`; independent of other packages). Local tests: `validation/test_s2.py` all true; artifacts + manage all true.
- **Applied** (user-approved, "Yes, install both") at 2026-10-02T03:16Z -> `{"completed": "apply", "backup": "/data/iq-warning-backups/20261002T031600.846237Z-apply", "services_restarted": false}`; `--verify-installed` passed. On-device hash: `b0c92a1ff212022be0506bad3f99675dcadf3669aadb66b2c8d73e4cbc56fb32`. Physical check pending: stopped-lead gaps ~+1.0 m vs the measured 1.8-3.0 m.

## P1 personality button fix (3736edc)

- 2026-10-02: built `tucson-personality-3736edc-P1/package` (`iqpilot/selfdrive/selfdrived/selfdrived.py`: `put_nonblocking` -> `put` on the gapAdjustCruise personality write, so the 100 ms params_thread re-read can no longer win the race and snap the value back). Local tests: `validation/test_p1.py` all true (deferred-write race sim: rollback reverts, candidate sticks; cycle 1->0->2->1); artifacts hashes + patch roundtrip + py_compile true; manage guards 7/7.
- **Applied** (user-approved, "Yes install that") at 2026-10-02T04:01Z -> `{"completed": "apply", "backup": "/data/iq-warning-backups/20261002T040118.183399Z-apply", "services_restarted": false}`; `--verify-installed` passed. On-device hash: `edf2fbee72d1541f50eb6c6c7654143fbecc0a6335910ce5e41a4d4b0dab457e`. Physical check pending: a distance-button press should cycle Standard->Aggressive->Relaxed->Standard instead of always showing Aggressive.

## tune-v6 hand-back friction reset (3736edc)

- 2026-10-02: staged `research/tune-v6-handback/package` at `/data/tucson-packages/v6/package/`; `--check` -> `{"check_passed": true, "changes_made": false, "head": "3736edc..."}`.
- Pre-install cross-check on routes 00000045/00000046 (first drives with L2+S2+P1, Experimental ON, Standard): steering clean (steerPressed 6.3% of active frames, saturation 0, steer faults 0, no new wobble episodes). No gapAdjust button presses in these drives, so P1 is still physically unverified.
- **Applied** (user-approved, "if all good install") at 2026-10-02T19:46Z -> `{"completed": "apply", "backup": "/data/iq-warning-backups/20261002T194644.754065Z-apply", "services_restarted": false}`; `--verify-installed` -> `{"installed_and_running_verified": true}`. On-device hash `0b6d5cf312706aeedbbee6fec2bf4fe02e584afa46f351b5b6668a31dffce102`. Live on next car start. Physical check pending: less tug in the first half-second after handing the wheel back / on lane-change exits.
- Longitudinal note from the same drives: every engaged stop behind a lead had `longitudinalPlanSource = e2e` (Experimental mode), so the MPC stop-distance constant S2 changed is not the active path; stop dRel at standstill was 1.2-1.4 m (one at 3.2 m) vs 1.8-2.8 m on earlier Aggressive/Experimental drives. S2 is not delivering the extra gap in Experimental mode; stop-gap work must target the e2e path (e.g. `IQCustomStopDistance`). Launch peaks 1.88-2.29 m/s^2 (4 launches), not clearly lower than pre-L2 1.7-2.3.

## cruise-E1 engage-at-current-speed + turn-aware e2e accel + set-drop coast (3736edc)

- 2026-10-02: staged `research/cruise-E1/package` at `/data/tucson-packages/E1/package/`. First `--check` failed on manifest guards, not on the device: `validation_dependencies` still listed the pre-L2 carcontroller hash and the pre-v6 latcontrol hash, and listed `cruise.py` (a target file) with its original hash, which makes `--verify-installed` impossible by construction. Fixed the manifest (deps now `carcontroller.py = 5a03012c…` (L2), `latcontrol_torque.py = 0b6d5cf3…` (v6); `cruise.py` removed from deps), CHECKSUMS updated, `test_artifacts.py` + `test_manage.py` still all true. Device run needs `PYTHONPATH=/data/openpilot/.venv/lib/python3.12/site-packages:/data/openpilot /data/openpilot/.venv/bin/python manage.py …` (system python3 lacks capnp).
- `--check` -> `{"check_passed": true, "changes_made": false, "head": "3736edc..."}`.
- **Applied** (user-approved, "Yes, install") at 2026-10-02T23:34Z -> `{"completed": "apply", "backup": "/data/iq-warning-backups/20261002T233441.590519Z-apply", "services_restarted": false}`; `--verify-installed` -> `{"installed_and_running_verified": true}`. On-device hashes: `cruise.py 9186434f643997d7516898abcca39e630c8b0cf55a200ae6bdb522f32f601080`, `longitudinal_planner.py 33788391e05af5429f8ac5cdab19947ed9aec2a374766f7dc6d16271604f24ae`. Live on next car start.
- Physical check pending: engage (SET/RES/+/-) adopts current speed rounded to 5, floor 25 mph (no 65, no crawl target); lowering the set speed by <10 mph coasts for 5 s instead of braking ~1.4 m/s^2; hard-turn e2e accel budgeted by lateral accel (route-48 3:37 lurch would have been capped ~1.9 -> ~0.3 m/s^2).
