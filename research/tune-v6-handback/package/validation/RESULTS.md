# tune-v6 validation results (offline)

- test_artifacts.py: all_three_file_hashes, forward_reverse_patch_roundtrip, py_compile — pass
- test_manage.py: all 7 transaction guards pass
- test_v6_equiv.py (real update() over 6000 replay frames, stubbed deps):
  - knobs off -> bit-identical to v5
  - split_ff_fb with fb factor == scheduled -> max abs diff 7.105e-15 (<1e-9)
  - configured v6 vs v5 -> max delta 0.0244 torque units, 0 frames > 1.0
    (deltas = knob-B friction ramp after steeringPressed/reversal; frames ~7.4 m/s)
- sims (analysis/tune-v6-split/work): see README/NOTES tables
