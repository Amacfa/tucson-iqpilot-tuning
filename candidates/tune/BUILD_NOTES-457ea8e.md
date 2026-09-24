# BUILD_NOTES — tucson-tune-457ea8e (rebase)

Rebase of `tucson-tune-0b8c190c/package` onto device HEAD
`457ea8e2d33eb3f48f5805b35e6dff9a046c312c`.

## What changed vs the 0b8c190c package

- `manifest.head` → `457ea8e2d33eb3f48f5805b35e6dff9a046c312c`; added
  `rebased_from_head` = `0b8c190c…` and `rebase_note`.
- `software_validation_passed` → true (offline scope only, recorded in
  `software_validation_scope`); `physical_validation_pending` stays true.
- forward.patch/reverse.patch: byte-identical (verified — all three rollback
  baselines still match the device byte-for-byte).
- README status section updated to match the new validation flag.
- CHECKSUMS.json regenerated (15 entries).

## validation_dependencies re-check against device (457ea8e)

Queried `sha256sum` on-device for every listed path. Mismatches found (listed,
not changed in the manifest):

- `artifacts/runtime/env_sync.sh`: manifest `41bc72c2…` → device `dc8f34c8cb354d78603630e12f3c05482bdcb1c3af2a524c12f77f0deda2e05f`
- `.iqpilot-package-lock-sha256`: manifest `099af809…` → device `f43a1c52b6448aad3a1ae4e36fce64c543729af69e98e3eb78ecc8e1c5f8cd11`
- `iqpilot/system/runtime_package_build.py`: manifest `5b4b25ec…` → **file missing on device** (sha256sum: No such file)
- `iqpilot/selfdrive/pandad/panda_safety.o`: manifest `59f18fb7…` → device `7ffb1c469e8df33983779735ec09808931478967c43ea8d198fce43a58170a1f` (rebuilt object, same source hash)
- `iqpilot/common/libcommon.a`: manifest `ace303b2…` → device `3e4808db99e3e6fa82245197c4936b78db69486761b317a30167743ddf680b8e` (rebuilt archive)
- `iqpilot/cereal/libsocketmaster.a`: manifest `5c10fd20…` → device `045f3765f3a9368af9ce811b3829debe8834a40af650c2c401f0d671ea64f5db` (rebuilt archive)
- `iqpilot/cereal/libcereal.a`: manifest `ba0139f0…` → device `dd836d7707df8c2b837f949b6d304d8cae6ab6ab5731cbe7d60470af1f10e969` (rebuilt archive)

All other entries (all Python sources, pandad.cc/panda_safety.cc sources, launch
scripts, uv.lock, main.o, libpanda.a, libmsgq.a, iqdbc sources, the three
rollback baselines) match the manifest exactly.

Consequence: `manage.py --check/--apply` will currently REFUSE on these
validation_dependencies until the manifest is updated or the gate is reviewed —
deliberate, per instructions not to silently change them.

## Tests (in package dir, /usr/bin/python3)

```
$ python3 test_artifacts.py
{"all_three_file_hashes": true, "forward_reverse_patch_roundtrip": true, "candidate_and_rollback_py_compile": true}
$ python3 test_manage.py
{"apply_rollback_exact": true, "partial_write_failure_restores_originals": true, "temporary_files_removed": true, "unrelated_edit_refused": true, "mixed_original_candidate_rollback": true, "receipt_failure_restores_originals": true, "guards_survive_python_optimization": true}
```
