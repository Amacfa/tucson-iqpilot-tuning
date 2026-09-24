# Arming/warning repair (no F1B) for release-candidate 0b8c190c

This package contains six candidate files and the six original files for rollback, pinned to IQ 0b8c190c59637d10ccd76525f6685c7d3b964264.

What it changes:

- Arming epoch invalidation on MAIN: pressing MAIN no longer silently reuses a stale arming state.
- Camera-MAIN is excluded as an authorization source.
- A fresh SET/RES press after a neutral-to-brake-clear transition is required to rearm.
- LFA stays inactive while arming is pending.
- A SAB availability gate is added.
- pandad publishes fresh health immediately after a safety transition (publication-order change), instead of waiting for the next 100 ms cycle.

User-visible behavior change: pressing MAIN alone will not rearm the system. You must press SET or RES. This is intentional.

F1B is NOT included in this package. The torque controller must remain the unmodified baseline; both the apply-time and post-install checks require the baseline controller hash.

manage.py defaults to check-only. --apply requires current parked/ignition-off telemetry, exact source/configuration match, no staged IQ update, and the baseline torque controller. --rollback restores all six original files; a normal parked restart is necessary. --verify-installed checks all six installed hashes, the import location, and the loaded pandad executable after restart. No controls are engaged by this installer. IQ updates can overwrite local patches; no automatic reapplication is installed.

Software validation: software_validation_passed is now true after the isolated route23 current-runtime replay on the device (see ../validation/route23 and BUILD_NOTES.md). Physical message timing, EPS acceptance and dashboard clearance still require a supervised parked ignition-on check after installation; physical_validation_pending remains true.
