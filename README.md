# Tucson comma/IQ.Pilot offline engineering record

Offline analysis and guarded install packages for a Hyundai Tucson (4th gen, CAN-FD)
comma/IQ.Pilot setup at release-candidate `0b8c190c59637d10ccd76525f6685c7d3b964264`.
Everything here was produced offline from exported drive logs; no device access was
involved and nothing is installed by this repo.

## Layout

- `reports/` — drive-log analysis reports (`REPORT.md`, `DEEP_RESEARCH.md`) and the
  arming-package README/BUILD_NOTES.
- `scripts/` — analysis and export scripts used to build the frame dataset
  (`export_drive_summary.py`, `analyze_*.py`, `build_long.py`) and the route23
  isolated replay tooling under `scripts/route23/`.
- `candidates/arming/` — guarded install package (manifest, manage.py, forward/reverse
  patches) for the arming/warning repair at 0b8c190c. `software_validation_passed`
  is false pending the isolated route23 runtime replay.
- `candidates/tune/` — guarded install package for the steering/longitudinal tune
  (speed-scheduled latAccelFactor + measurement low-pass, CAN-FD jerk_u floor/boost,
  friction 0.108745 -> 0.12). Must be applied after the arming package.
- `candidates/fingerprint/` — the CW020 camera fingerprint candidate patch and its
  notes (patch/diff and report only).

## Safety notes

- `manage.py` in each candidate package defaults to read-only `--check`; `--apply`
  refuses while `software_validation_passed` is false and requires a parked,
  ignition-off device with exact version and parameter pins.
- Sensitive data (route IDs, dongle IDs, IPs, keys, params dumps) has been stripped
  or redacted; binary exports (.npy/.jsonl.gz/rlog) are intentionally not included.
