# Tucson CW020 automatic recognition — 2026-09-22

**The minimal firmware-table candidate passes the actual IQ runtime matcher and configuration checks.** It recognizes this owner's recorded ECU combination as `HYUNDAI_TUCSON_4TH_GEN` without a manual fingerprint. Automatic recognition has not yet been observed on a fresh physical ignition cycle in this subtask. No device files, settings, CAN traffic or services were changed by this validation.

## Change and evidence

Pinned current IQ release-candidate: `3636baa7f44ecef89163d75a93ccfc201454e0d8`.

The recorded camera response is:

```python
b'\xf1\x00NX4 FR_CMR AT USA LHD 1.00 1.00 99211-CW020 14Z'
```

The recorded distinguishing radar response is:

```python
b'\xf1\x00NX4__               1.01 1.00 99110-N9100         '
```

The current database already recognizes the radar under Tucson and the camera under Santa Cruz. It lacks that exact camera response under Tucson. The runtime change adds only that exact byte string to the existing Tucson camera list. There are no wildcard, query, matching-rule, essential-ECU, geometry, tuning or safety-limit changes.

The existing historical CW blacklist test now exempts only this complete Tucson response, with an explicit tuning-history comment. `test_tucson_cw020.py` exercises the actual public all-brand matcher. The camera alone never establishes the platform; both the camera and distinguishing radar remain essential. Two conflicting radar families remain ambiguous, and the existing production caller only selects firmware identification at exactly one candidate.

The normal database is per ECU, so this addition permits the camera with all four existing Tucson radar versions. Only the captured N9100 1.01/1.00 combination has direct evidence from this vehicle. The other three combinations are tested for identification uniqueness, not their physical existence or steering behavior. The two existing Santa Cruz radar versions continue to select Santa Cruz. No EPS entry is added; EPS is not a matched essential ECU in these CAN-FD platform tables.

## Native validation

`native-result-02.json` records a successful, isolated process on the comma, with fresh ignition-off guards, publishers/network denied and private Params. Protected live state is identical before and after and temporary files were removed.

- All 14 expected firmware brands/configs imported successfully, covering 244 vehicle firmware tables. Explicit direct imports prevent optional import failures from silently shrinking the matcher population.
- Replayed the full 18 CarFw records from the earlier IQ unrecognized startup, retaining their brands, addresses, requests, bus, logging and multiplexing fields. Baseline returned no match; the candidate returned exactly Tucson. `VIN_UNKNOWN` was used.
- Eight full-record negative cases reject a missing, unknown, logging-only or wrong-brand camera/radar. Reordering or duplicating all records preserves the exact Tucson match.
- Six publishable test methods pass, including 148 matcher assertions over the known camera/radar matrix, invalid/missing data, Santa Cruz positive controls, unchanged Tucson entries and conflicting-radar ambiguity. Other CW versions and even a changed revision of CW020 do not enable Tucson.
- Incremental native execution of the complete existing `test_hyundai.py`, with the exact candidate table and revised blacklist exception, passes **13 tests and 384 subtests**. Evidence: `existing-tests-result-02.json`; execution uses private Params, an isolated working directory/Hypothesis store and explicit `pytest_subtests.plugin`, with the manager cleanup plugin disabled. Protected live state is unchanged and temporary files are removed. Attempt 01 had eight passing tests and five setup errors because loading `pytest_subtests` instead of its `.plugin` did not register the fixture; there were no candidate assertion failures, and candidate bytes did not change.
- Four saved CAN fingerprints from the earlier unrecognized IQ startup and a working manual-Tucson startup produce **identical complete generated CarParams and IQCarParams** when comparing automatic candidate plus firmware against the manual Tucson candidate with no firmware. These are repeated captures from two sessions, not four independent vehicles.
- The configuration check executes actual `CarInterface.get_params`, `get_params_iq`, IQ port configuration, final IQ application and AOL flag/brand functions with private copies of the current relevant settings. It checks flags 8206, extFlags 132, safetyParam 44, alternativeExperience 1024, IQ flags 4/safety flags 32, enabled longitudinal control, non-HDA2 camera SCC/alternate buttons and native limits 270/2/3.

The native check does not invoke a real firmware query, `CarInterface.init`, optional device initialization, a publisher, manager or service restart. Comparison covers generated control configuration; source/firmware/VIN metadata are assigned by the caller afterwards. It does not prove steering response, firmware timing, a new physical identification or dynamic ALT2 detection. The saved frames and working profile establish the relevant current input configuration; existing warning/F1B validations remain separate.

Run 01 failed only in the test harness after matcher tests: redirecting Params with a function broke a runtime `Params | None` annotation. Run 02 uses a constructor proxy class, leaves the candidate unchanged and passes. Both runs preserved the live device state.

## Historical restriction and present scope

CW Tucson entries were previously excluded over unresolved steering tuning/scaling, not merely overlooked. The prior history review documents openpilot PRs 27340/28318 and opendbc issue 1115. The exact CW020 proposal in opendbc PR 1601 closed for inactivity; that is not evidence of a measured defect in this exact response. See the preserved `analysis/tucson-fingerprint-2026-09-18/HISTORY_REVIEW.md`.

This IQ-specific proposal accompanies the owner's subsequently tested correct Tucson profile, Teal's feedback fixes and the separately restored F1B/warning package. It should not claim to validate all CW-equipped Tucsons or resolve upstream's fleet-wide tuning concern. Recognition tests alone do not establish controller suitability. The owner previously reported substantially improved steering under the correct manual profile; this change removes that owner's manual identification requirement without changing the selected profile.

## Activation boundary

The present manual `CarPlatformBundle` makes the production caller skip firmware querying. Installing the new table alone therefore cannot prove automatic selection. The parent task owns backing up that exact bundle, selecting the UI-equivalent automatic mode, preserving the seven installed fixes and verifying a fresh parked ignition cycle. Preserve calibration and learned parameters. Fresh `fingerprintSource=fw`, unique Tucson, the expected configuration and healthy startup are the physical acceptance checks; an unreachable/off-ignition device is not a successful recognition result.

## Artifacts and privacy

Candidate runtime table SHA-256: `19d864059fbc1486b563b0fc88a2f41e5e7c8fc86d11ec9789e5d3ac32534a99`.

`candidate/iqdbc/car/hyundai/fingerprints.py`, the modified `tests/test_hyundai.py` guard and new `tests/test_tucson_cw020.py` are suitable for the source PR. The tests contain only public firmware/model constants, no VIN, dongle ID, route code, coordinates or private fixture path.

`private-inputs.json`, native result/probe data and private payloads stay local. `source-manifest.json` and `final-manifest.json` pin source and evidence. Reviewer-owned `../review/check_fingerprint_scope.py` independently checks the one-entry diff and exact blacklist exception, including rejection of nearby variants.
