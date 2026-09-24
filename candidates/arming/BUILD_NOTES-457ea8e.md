# BUILD_NOTES — tucson-warning-arming-457ea8e (rebase)

Rebase of `tucson-warning-arming-0b8c190c/package` onto device HEAD
`457ea8e2d33eb3f48f5805b35e6dff9a046c312c`. Device self-updated from 0b8c190c;
`git diff --stat` shows release 457ea8e changed only UI/system/iqmodeld files —
all six package source files are byte-identical to the 0b8c190c baselines.

## What changed vs the 0b8c190c package

- `manifest.head` → `457ea8e2d33eb3f48f5805b35e6dff9a046c312c`; added
  `rebased_from_head` and `rebase_note`. `software_validation_passed` stays true
  (sources unchanged).
- `files[]` pandad entry: original → `07184998ce24d92f2fbd0099913405e42188eab8ce95fbdbc61bae9e62dce505`,
  candidate → `9ca10a2f57f27b465ba3d41b33757e12bd71ad7ab775ae51850ac4e60788e2ce`.
- `rollback/iqpilot/selfdrive/pandad/pandad` replaced with the device's current
  binary (sha256 verified `07184998…`); `candidate/…/pandad` replaced with the
  on-device rebuild (`9ca10a2f…`).
- Grep confirms no remaining references to old hashes 8bc7cf63/a4bf4daa —
  native_build_dependencies/validation_dependencies never listed the pandad
  binary itself.
- forward.patch/reverse.patch: byte-identical to 0b8c190c versions (verified —
  pandad binary is not in the patches; all four text sources unchanged).

## pandad rebuild provenance (device, /data/tucson_stage)

- Compile flags from device `compile_commands.json` (clang++ 18.1.3, -std=c++1z
  -O2 -g -fPIC -D__TICI__ -mcpu=cortex-a57 -DQCOM2 -DPANDA_FW_PATH=..., include
  set per SConstruct). scons is not installed; link line reconstructed from
  SConscript/SConstruct: `main.o pandad.o panda_safety.o libpanda.a -lusb-1.0
  -lcommon -ljson11 -lzmq -lsocketmaster -lmsgq -lcapnp -lkj -lpthread` with
  `-Wl,--as-needed -Wl,--no-undefined`.
- Reproducibility: baseline rebuild of shipped pandad.cc yields a binary
  byte-identical to the shipped pandad after stripping debug info except the
  20-byte .note.gnu.build-id (comp_dir /data/openpilot vs /data/iqpilot symlink
  difference). Candidate built the same way from candidate pandad.cc.
- Candidate binary `9ca10a2f…`: aarch64 PIE, `ldd` fully resolved, not executed.

## Tests (in package dir, /usr/bin/python3)

```
$ python3 test_artifacts.py
{"all_six_file_hashes": true, "forward_reverse_patch_roundtrip": true, "source_and_installed_iqdbc_match": true}
$ python3 test_manage.py
{"apply_rollback_exact": true, "partial_write_failure_restores_originals": true, "temporary_files_removed": true, "unrelated_edit_refused": true, "mixed_original_candidate_rollback": true, "receipt_failure_restores_originals": true, "guards_survive_python_optimization": true}
```

CHECKSUMS.json regenerated (19 entries).
