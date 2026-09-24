# INSTALL_LOG — device install of both 457ea8e packages

Device HEAD: `457ea8e2d33eb3f48f5805b35e6dff9a046c312c`. Installs run on the comma
from `/data/tucson_stage/` with the device venv python.

## Timeline

- **2026-09-24 07:39:42Z** — arming package `--apply`
  (backup `/data/iq-warning-backups/20260924T073942.872889Z-apply`)
- **2026-09-24 07:40:05Z** — tune package `--apply`
  (backup `/data/iq-warning-backups/20260924T074005.858580Z-apply`)
- Reboot after both applies.

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
