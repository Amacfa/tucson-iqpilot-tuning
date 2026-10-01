# M1 — Tucson MAIN-button no-disarm (offline candidate, NOT installed)

## Problem
On HYUNDAI_TUCSON_4TH_GEN (CAN-FD, camera-SCC, alt-button layout, openpilot-long),
pressing the **MAIN** cruise button while the comma is on turns it fully off:
the arming package's carstate latches `main_enabled` off on any MAIN press and the
legacy MAIN-release toggle flips it again, so `cruiseState.available` drops 1→0 and
the comma is unusable until the next SET/RES release. Logged occurrences:
route 0x3a seg1 @47.8 s, route 0x3b seg1 @46.5 s, route 0x3b seg2 @39.4 s.

## Change (candidate files)
- `iqpilot/sab/behavior.py` — new `_tucson_guarded()` helper (fingerprint +
  openpilotLongitudinalControl + CANFD_ALT_BUTTONS), shared by the existing
  `_phase_tucson_native_main_gate` and a new rule at the top of `_phase_buttons`:
  on `mainCruise pressed` while guarded — emit `alcDisengaged` if a lateral session
  is on, never emit `alcEngaged` from MAIN, never `kill_all` (longitudinal keeps
  running; panda keeps `controls_allowed` for SET/RES-cancel semantics).
- `iqdbc/car/hyundai/carstate.py` (installed at **both**
  `artifacts/package_sources/...` and `.venv/.../site-packages/...` paths):
  - inside `if tucson_release_gate:` the MAIN-press latch
    (`main_enabled and (buttons) → _tucson_main_off_latched = True`) is removed —
    MAIN no longer stops advertising ready. SET/RES-release arming,
    `main_release_pending` precedence, and the `main_quiet` reset are unchanged.
  - the release gate is stored as `self._tucson_release_gate` at computation time
    (init `False` in `__init__` next to `_tucson_main_off_latched`).
  - the legacy MAIN-release toggle now skips its off-direction only when
    `_tucson_release_gate` is armed and `main_enabled` is already True
    (MAIN still turns main **on** when it was off).

## Panda consistency (no firmware changes)
- `hyundai_common.h`/`aol.h` semantics: MAIN toggles panda `acc_main_on`;
  **falling edge drops panda lateral permission, rising edge grants it**;
  longitudinal `controls_allowed` is unaffected by MAIN (granted by SET/RES
  release, dropped by CANCEL).
- Therefore the app must end its lateral session on a MAIN press (panda already
  revoked lateral), must not grant lateral from MAIN (it cannot know the panda
  `acc_main_on` parity), and must leave longitudinal untouched.

## Expected driver-facing behaviour
- **MAIN while on**: steering session ends (alcDisengaged), gas/brake ACC keeps
  running, comma stays armed (`cruiseState.available` stays 1).
- Steering returns on a **SET release** (or MAIN again plus a wheel button, which
  re-arms `main_enabled` then lets SET release re-engage).
- **MAIN while off**: arms as before — unchanged.

## Status
**NOT installed. Physical validation pending.** `readiness: check_only`.
Requires the warning-arming package installed (base bytes = its candidate).
Rollback restores those base bytes exactly.

## Validation (offline, this box)
`validation/test_m1.py` (plain python3, stubbed deps): Tucson+enabled+MAIN →
`alcDisengaged` + `kill_all=False`; enabled=False → silent; LFA path unchanged;
non-Tucson CP → identical to base; toggle-block cases exec'd verbatim
(gate+armed release keeps `main_enabled`; gate+off release toggles on;
no-gate toggles both ways); latch deletion asserted; py_compile clean.
Plus `test_artifacts.py` (hashes + forward/reverse patch roundtrip) and
`test_manage.py` (7 guard tests) — all pass.
