# Tucson LFA warning stationary A/B switch (hyundaicanfd) — release 3736edc

Status: check_only. software_validation_passed = true (offline only);
physical_validation_pending = true.

Single target file:
`.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/hyundaicanfd.py`

The candidate adds a bitmask read once per CarController start from
`/data/tucson_lfa_ab` (a plain file, no Params key). Missing or invalid file
=> variant 0 => byte-identical behavior to the stock release (verified
offline: variant-0 output == orig output for frames 0/5/10/500, lat_active
both).

Bits:
- 1: LFA (0x12a) built from the camera's own frame; only LKA_ICON /
     TORQUE_REQUEST / STEER_REQ / DampingGain are overridden with IQ's values.
- 2: MDPS (0xea) relayed to the camera bus unmodified — no LKA_ACTIVE rewrite
     and no hands-on spoof (also disables the STEER_TOUCH_2AF spoof).
- 4: LFAHDA_CLUSTER (0x1e0) passed through unless IQ is actively controlling
     (HDA_LFA_SymSta / HDA_CntrlModSta forced to 2 only while active).
- 8: DampingGain kept at the camera's value (100) while IQ steers.

Operation:
- `set_variant.sh <0-15>` writes /data/tucson_lfa_ab on the comma.
- The file is read once at CarController construction, so EVERY variant
  change needs a parked IQ restart (reboot) to take effect.
- Missing file = variant 0 = release behavior.

manage.py is identical in behavior to the tune v2 package manager:
--check / --apply / --rollback / --verify-installed, parked() + head pin +
required_params + validation_dependencies gates, atomic transaction with
backup under /data/iq-warning-backups/, no service restarts. On apply it also
accepts this file's stock hash only (no tune package modifies it).

validation/: py_compile, forward/reverse patch roundtrip, and
test_variants.py — a DBC-driven unit test over all variant bits including the
panda-safety invariants (STEER_REQ==0 when not lat_active, TORQUE_REQUEST==
apply_steer) for variants 0,1,2,4,8,15.
