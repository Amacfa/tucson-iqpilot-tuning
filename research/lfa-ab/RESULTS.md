# tucson-lfa-ab-3736edc — validation results (offline only, nothing installed)

## test_artifacts.py (package/)
{"all_three_file_hashes": true, "forward_reverse_patch_roundtrip": true, "candidate_and_rollback_py_compile": true}

## test_manage.py (package/)
{"apply_rollback_exact": true, "partial_write_failure_restores_originals": true,
"temporary_files_removed": true, "unrelated_edit_refused": true,
"mixed_original_candidate_rollback": true, "receipt_failure_restores_originals": true,
"guards_survive_python_optimization": true}

## validation/test_variants.py — all_passed
{"variant0_identical_to_orig": true,
"missing_or_invalid_variant_defaults_0": true,
"bit1_lfa_passthrough": true, "bit1_lfa_len_same_as_v0": true,
"bit2_mdps_unmodified": true, "bit2_touch_unmodified": true,
"bit2_lka_active_not_rewritten": true,
"bit4_cluster_inactive_passthrough": true, "bit4_cluster_active_forced_2": true,
"bit8_damping_100_when_active": true,
"v0_damping_0_when_active": true, "v0_cluster_forces_0": true,
"panda_safety_sanity_all_variants": true}

Variants tested: 0,1,2,4,8,15 across frames 0/5/10/500, lat_active both.
Variant 0 output is byte-identical to the orig module for the same inputs.
Panda sanity asserted for every variant: LFA STEER_REQ==0 when not lat_active,
TORQUE_REQUEST==apply_steer.

## Stubbing disclosures (local box limits)
- No capnp locally: iqdbc.car package objects stubbed with __path__ into the
  pulled device pydeps/ tree; minimal CanBusBase + CanBus (offset=4*(N-1));
  HyundaiFlags/ExtFlags stubbed with real values; iqpilot.common.params
  (get→None) and iqpilot.cereal.log stubbed.
- python3.10 lacks ReprEnum/StrEnum/EnumType/dataclass_transform — shimmed.
- cantools 44.1.0 CANNOT load the generated hyundai_canfd DBC (signals declared
  beyond message length, strict=True fails; lenient encode crashes on >DLC
  bits). test_variants.py therefore implements a minimal BO_/SG_ parser +
  sawtooth-MSB Motorola + LE Intel packer. Encode/decode are self-consistent
  (variant-0 byte-identity vs orig proven on the same packer), but byte-level
  equivalence vs the device's C++ CANPacker is NOT verified — e.g. real
  CHECKSUM computation is skipped (asserted as 0 on both sides).

## Candidate review (user's file, logic unchanged — no real bug found)
- Variant cached at first call; missing/invalid file -> 0 + carlog.warning.
- bit1: copy.copy(CS.lfa) + overrides LKA_ICON/TORQUE_REQUEST/STEER_REQ/
  DampingGain/NEW_SIGNAL_2(=STEER_TOUCH_2AF); pops COUNTER so packer refills
  via rx_counter. Preserves camera COUNTER value is lost — intentional
  (frame must carry cycle counter).
- bit2: relays CS.mdps unmodified (incl. its own LKA_ACTIVE), skips
  STEER_TOUCH_2AF hands-on spoof; CS.lfa STEER_REQ=1 no longer forced to
  LKA_ACTIVE=0.
- bit4: LFAHDA_CLUSTER keeps camera HDA_LFA_SymSta/HDA_CntrlModSta unless
  either control is active (then forced 2/2 as stock does when active).
- bit8: DampingGain=100 while lat_active (stock forces 0); bit4 gate
  ((... & 0x0C)!=0) still wins if both set? No — damping line evaluates
  `100 if ab&8 else (0 if active else 100)`; bit4 unchanged semantics.

Minor observation, not a bug: when bit1 set and camera LFA lacks an
overridden key (e.g. malformed decode), copy.copy keeps camera's stale
LKA_ICON — only relevant on corrupted input; acceptable.

## Hand-verified before build
- v2 tune manifest's files[] does NOT include hyundaicanfd.py (only listed
  under validation_dependencies at stock hash) — no file overlap.
- manifest validation_dependencies refreshed to live 3736edc device hashes
  (carried over from the arming/tune-3736edc manifests).
