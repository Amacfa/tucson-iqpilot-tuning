Tucson CW020 camera fingerprint — release 457ea8e (check only)

Status:
- Baseline iqdbc/car/hyundai/fingerprints.py is byte-identical to the device at
  HEAD 457ea8e (dd31c382…, both install locations).
- The candidate adds the observed fwdCamera FW string
  "f1\x00NX4 FR_CMR AT USA LHD 1.00 1.00 99211-CW020 14Z" under
  HYUNDAI_TUCSON_4TH_GEN. In stock 457ea8e that string exists only under
  HYUNDAI_SANTA_CRUZ_1ST_GEN, so the candidate is still required.
- readiness=check_only; software_validation_passed=true (offline: hashes,
  patch roundtrip, py_compile). Physical check pending: parked
  fingerprintSource == "fw" + fingerprint == HYUNDAI_TUCSON_4TH_GEN.

Files changed by apply:
- artifacts/package_sources/iqdbc/iqdbc/car/hyundai/fingerprints.py
- .venv/lib/python3.12/site-packages/iqdbc/car/hyundai/fingerprints.py

Gate: --apply/--check refuse unless parked() (offroad, not started, one panda,
no ignition/controlsAllowed) and supported_configuration() (HEAD == 457ea8e,
required_params, validation_dependencies) hold.

Caveat: the CW020 fwdCamera FW string is also listed under
HYUNDAI_SANTA_CRUZ_1ST_GEN in stock 457ea8e; adding it to TUCSON_4TH_GEN
makes both fingerprints matchable by camera alone, so FW fingerprinting
still relies on the other ECUs to disambiguate. Status: --check passed on
device 2026-09-24; check-only, NOT installed.
