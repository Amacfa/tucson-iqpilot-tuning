# BUILD_NOTES — tucson-warning-arming-0b8c190c

Built 2026-09-24 UTC, offline, cloned from
`/home/ubuntu/tucson/analysis/tucson-warning-f1b-install-20260922/package/`
into `/home/ubuntu/tucson/analysis/tucson-warning-arming-0b8c190c/package/`.

Six files (the F1B `latcontrol_torque.py` entry was dropped intentionally).
`torque_controller_sha256` and `candidate_controller_sha256` are both set to the
baseline controller hash `6578845cf1f7f138203eade26eb9dc301bfe221d66272f81bb095bf9788aec31`,
so `--apply` and `--verify-installed` both require the unmodified controller.

`software_validation_passed` is `false` and `runtime_validation_pending` is `true`:
manage.py refuses `--apply` until the flag is flipped after the isolated route23
runtime replay.

## File inventory (sha256)

### rollback/ (originals)
- `iqpilot/selfdrive/pandad/pandad` — `8bc7cf6325258684c7c2decbcb4a7d9a6e0d3673fbd79c10ef30d47b29c8c5da` (copied from old package rollback)
- `iqpilot/selfdrive/pandad/pandad.cc` — `4266f837f75f3c8d2c6fa22c3ba21054aae2ce04e4e5e9670c6316392e6ae00f` (copied)
- `iqpilot/selfdrive/car/card.py` — `66b945442437decc94ab68d412d71a84e0d23d32680fd8cafe771a151bf0cae2` (copied)
- `iqpilot/sab/behavior.py` — `aa0341544c2ee0b14d7e928418dba8203c526d29bbf7b2b643e1d5c0c29a9f4b` (copied)
- `artifacts/package_sources/iqdbc/iqdbc/car/hyundai/carstate.py` — `7d62ff2eea091340fa65153a70dc137c8d07c60df6c5128d83761133bb9500ac` (copied)
- `.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carstate.py` — `7d62ff2eea091340fa65153a70dc137c8d07c60df6c5128d83761133bb9500ac` (copied)

### candidate/ (new)
- `iqpilot/selfdrive/pandad/pandad` — `a4bf4daa9130b780907fe4664135457d78924deeb654e3396fc755a3ccbe66a9` (copied from old package candidate)
- `iqpilot/selfdrive/pandad/pandad.cc` — `a66a2bafdc6a397a7eb9315662995caf88bad2410cf0a1ef909e1c21d9f5e466` (copied)
- `iqpilot/selfdrive/car/card.py` — `b993c28077a955fa056a835f95f79fa11cb42695843dfafdf2d96cea810431ba` (from `tucson-postfix-candidates-20260923/startup/candidate/`)
- `iqpilot/sab/behavior.py` — `44d607471d712837edf96f865a8537a7fcd4a972f9eb785abe104f2557857326` (copied)
- `artifacts/package_sources/iqdbc/iqdbc/car/hyundai/carstate.py` — `e361a10649ef2c64750e96df955d7e22b6674832c0393e328210741e32f41449` (from postfix candidates; identical bytes in both locations)
- `.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carstate.py` — `e361a10649ef2c64750e96df955d7e22b6674832c0393e328210741e32f41449`

### Package files
- `forward.patch` — `fa0e6e327e9ad81f6ad0768e290c6b8dd98d5bf26ee64752c83a138ccb781fd6`
- `reverse.patch` — `4b5f13cf599b3af07a37a7006755172691853e8670b8a946c6ecce2483be11e1`
- `manage.py` — `8fd03272bccd0af846a80b83ce960666a1bbf6c59abb35b83a8001e11a116720` (identical to old package)
- `manifest.json` — `388b17f759e44335bb1be5635897f5cf73b175ff7d8d07be685e2924a4b38176`
- `README.md` — `87388fef36605216193471d11d61754d29a73179cc0470bd66a9390fe7bfddff` (rewritten)
- `test_artifacts.py` — `fb41dfd0d77d63eeb11e5c3ede807b499a42ed711b02cb48658627d2fc437ae4`
- `test_manage.py` — `6b7c2e41314a7023187b5b651407057d6a78f1ee64b71fb120eeeb39cfcb1aa6` (identical to old package)
- `CHECKSUMS.json` — regenerated over all files above.

## Changes to copied scripts

- `manage.py`: copied unchanged (byte-identical, sha256 matches old package).
- `test_manage.py`: copied unchanged.
- `test_artifacts.py`: one edit — final print key `all_seven_file_hashes` → `all_six_file_hashes`.
- `forward.patch`/`reverse.patch`: regenerated with `diff -u --label a/<path> --label b/<path>` per file (same no-`diff --git`-header format as the old patches) for the four non-.venv text files (pandad.cc, card.py, behavior.py, artifacts carstate.py), in the same file order as the old patch.
- `manifest.json`: head set to `0b8c190c59637d10ccd76525f6685c7d3b964264`; name, created_utc, software_validation_passed=false, runtime_validation_pending=true, physical_validation_pending=true, F1B_installed=false, F1B_candidate=false, original_controller_retained=true, baseline controller hash in both controller fields, six-entry files[]. `readiness` set to `blocked_pending_isolated_runtime_replay` (old value `ready_for_supervised_parked_installation` no longer applies). required_params, fingerprint, flags, safety_param 44, alternative_experience 1024, native_build_dependencies and validation_dependencies copied verbatim.

## Tests run (/usr/bin/python3, in package dir)

```
$ python3 test_artifacts.py
{"all_six_file_hashes": true, "forward_reverse_patch_roundtrip": true, "source_and_installed_iqdbc_match": true}

$ python3 test_manage.py
{"apply_rollback_exact": true, "partial_write_failure_restores_originals": true, "temporary_files_removed": true, "unrelated_edit_refused": true, "mixed_original_candidate_rollback": true, "receipt_failure_restores_originals": true, "guards_survive_python_optimization": true}
```

`python3 -m py_compile` run on all four candidate .py files, all four rollback .py
files, and the three package scripts: all clean (PY_COMPILE_OK).

`git apply --check` of forward.patch against rollback-seeded temp dir, apply of
forward.patch, and apply of reverse.patch back to rollback hashes are covered by
test_artifacts.py (forward_reverse_patch_roundtrip: true).

## Isolated current-runtime replay (route23) — 2026-09-24 04:14–04:20 UTC

Executed on the comma (`iq-66480b62`, HEAD `0b8c190c`, parked, IsOnroad=0, ignition off,
card/controlsd not running) via Mac jump host with strict host verification. Driver
`validation/route23/route23_isolated.py` = unchanged `guard.py` (parked preflight, protected-state
snapshot before/after, publisher/network denial, private Params under /tmp, staged files removed)
+ `staged_runner.py` + `runtime_arming_runner.py`. `protected_state_unchanged: true`, `error: null`
on both runs; result `validation/route23/result-02.json.gz`
(`218100e176ab74f4311256125b526ce409f905831b3c35b56039d46ebb921000`).

Fixture: route `00000023--<redacted>` segments 0–2, 0–125 s, exported on-device from raw rlogs
(`export_route23_fixture.py`, bounded per-event decode, sorted by publication time, 15,025
reversals repaired), sha256 `162f10482e400fbb6405978d076e7805a77c89bf46704de7c3ce7d1417a8cb70`.
Recording embeds gitCommit `0b8c190c` / `release-candidate`, so parsed CarState/carControl in the
logs are from the same source the replay uses.

Pipeline per 100 Hz CarState tick, original and candidate side by side, same CAN input:
installed `iqdbc.can.parser.CANParser` → CarState (`7d62ff2e` original / `e361a106` candidate) →
`CarInterfaceBase.update` → `sab_bridge` (CarSpecificEvents, VehicleEvents, StateMachine,
SteeringAssistanceBehavior original/candidate `44d60747`, IQControlsLayer gate, fault recovery) →
`card.controls_update` extracted by AST from card.py (`66b94544` original / `b993c280` candidate,
candidate also runs `_sync_startup_arming` with the recorded pandaStates) → installed
`CarController` (`6f28ff93`, STEER_MAX/UP/DOWN asserted 270/2/3) → LFA captured from the inert
`pm.send`. Recorded actuator torque, vEgo, EPS fault bits and pandaStates are frozen input.

Results (`check_native_policy.py` → `native-policy-02.json`, harness.c `1d01c98a…` compiled on
Linux; all eight safety sources hash-identical on device):

| | original | candidate |
|---|---|---|
| ticks / canValid | 12,363 / 12,347 | 12,363 / 12,346 |
| cruiseState.available mismatch vs recorded (t≥10 s) | 0 ticks | 4,384 ticks (all intended, see below) |
| LFA frames generated | 12,220 | 11,740 |
| original vs recorded sendcan LFA (torque ±2, request) | 99.43 % (11,433/11,499) | – |
| rejected by unchanged policy | 1,103 frames, 21 spans 78.36–114.54 s | 0 |
| active frames inside 78.355–114.685 s | 1,344 | 0 (3,633 inactive torque 0/request 0 frames) |
| first active frame / native controls_allowed | 65.44 s / 114.689 s | 115.598 s / 114.689 s |
| post-SET parity 114.69–125 s | 1,031/1,031 ticks identical latActive, long_enabled, LFA torque+request |

Original reproduces the drive: MDPS-rejected spans start 78.360 s (61 frames), then 80.054,
81.751, 83.030, … 114.018 s — matching the 20 recorded fault intervals. Candidate arm_pending
stays true 1.325–114.689 s and clears only on the recorded SET release (decelCruise pressed
114.571 → released 114.689, brake clear); thereafter both runs are identical.

Behaviour change to disclose: the driver pressed camera MAIN at 65.37 s (native main on, AOL lat
allowed) and the baseline steered accepted 65.44–78.35 s on MAIN only. The candidate deliberately
does not arm on MAIN (parity is unobservable — the 78.355 s MAIN press turned native main OFF while
the app re-enabled) and therefore stayed inactive 65.44–78.35 s; steering requires a SET/RES release
after any MAIN activity. Native policy grants controls_allowed on every SET/RES release with
longitudinal enabled, so candidate permission ⊆ native permission in this replay.

Not covered: route23 has no brake, cancel or resume after the 114.69 s engagement; braking parity
is only shown while unarmed (6 brake intervals, identical long_enabled=false in both). Startup: the
recording's pandaStates switched to hyundaiCanfd/44 only at 7.596 s, so the candidate's first LFA
is 7.598 s vs 2.645 s baseline — faithful to frozen input, not a timing claim for the installed
pandad. Offline replay of source policy is not flashed-Panda, EPS or dashboard evidence;
`physical_validation_pending` remains true.

Metadata updated: `software_validation_passed=true`, `runtime_validation_pending=false`,
`readiness=ready_for_supervised_parked_installation`, `runtime_validation{}` block added;
README line 20 rewritten; CHECKSUMS.json regenerated (only README.md and manifest.json changed).
`test_artifacts.py` and `test_manage.py` re-run clean. Not installed; nothing restarted.
`validation/route23/route23-metadata-pubtime.json` contains the recorded Params snapshot — private,
do not publish.
