# Tucson steering/longitudinal tune (A2 + B + L1) for release-candidate 0b8c190c

Three candidate files and three originals for rollback, pinned to IQ 0b8c190c59637d10ccd76525f6685c7d3b964264.

## What it changes

**latcontrol_torque.py (A2)** — Speed-scheduled lateral acceleration factor plus a measurement low-pass. The stock controller uses one fixed latAccelFactor (2.960174) at all speeds. Logged drives show the car over-delivers small requests and under-delivers large ones: actual/desired lateral acceleration ran 1.09–1.24 at >=10 m/s but only 0.78–0.92 for small requests. The candidate interpolates the factor through (8, 15, 25) m/s → (2.95, 3.35, 3.70), so less torque is spent per unit of requested acceleration at speed. It also feeds the feedback error a 0.06 s first-order low-pass of measured lateral acceleration instead of the raw signal, to calm the response to noisy measurements.

Interaction with the live torque learner: controlsd calls `update_live_torque_params` before `update()` whenever `lateralTorqueParameters.useParams` is true; the schedule then overwrites `latAccelFactor` inside `update()` every frame, so the scheduled factor always wins while live offset/friction would still be honoured. On this car the learner has never reached `useParams` (all logged routes carry the static 2.960174 / 0.108745), so in practice the packaged 0.12 friction is what runs. The measurement low-pass is only created when `IQHkgReducedTorqueFeedback` is on (it is on this device) and is re-seeded to the raw measurement on every inactive frame, so engagement starts with zero filter lag.

**carcontroller.py (L1)** — CAN-FD longitudinal jerk_u floor and raw-request boost. The logged accel step ratio was 0.60 versus 1.21 achievable, meaning positive acceleration requests were being held to the ~0.5 m/s^3 MPC jerk ramp after the jerk term settled. The candidate keeps a 1.0 floor and adds a raw-request boost `clip(1.0 + 2.0*max(0, accel - 1.0), 1.0, 5.0)`, taking the max with the MPC term `clip(jerk*2.0, 1.0, 5.0)`. jerk_l (deceleration authority) is unchanged.

**params.toml (B)** — Tucson friction parameter 0.108745 → 0.12. The logged data showed roughly 45% of frames with 0.1-degree angle steps producing 1.4–1.9 unit torque jumps; raising the friction term compensates the stick-slip behavior at small torque requests.

## How to use

`python3 manage.py` (or `--check`) is read-only and verifies the head commit, parked state, params, and file hashes. `--apply` atomically replaces all three files (with automatic restore on any failure); `--rollback` restores the originals; `--verify-installed` re-checks installed hashes after a parked restart. No services are restarted and no controls are engaged by this installer.

## Ordering constraint (arming package)

`requires_arming_package_installed` is true. The arming package's `--verify-installed` pins the baseline hash of `iqpilot/selfdrive/controls/lib/latcontrol_torque.py`. This package replaces that file, so the arming package must be applied and verified **before** this package; afterwards, that arming-package hash check will no longer match by design (use this package's candidate hash `bb3f78b1…` for latcontrol_torque.py instead).

## Status

`software_validation_passed` is **false** and `physical_validation_pending` is true: validation so far is offline arithmetic only — physical A/B testing is still pending — so manage.py refuses `--apply` until the flag is flipped after sign-off.

Offline open-loop replay results are in `validation/RESULTS.md` (717,248 active frames >=5 m/s). Mean |torque| candidate vs reconstructed baseline by speed bin: 0.99 at 5-10 m/s (unchanged by design — output there is saturated at the |out|=1.0 clip), 0.94 at 10-15, 0.89 at 15-20, 0.84 at 20-25, 0.81 at 25+. Frame-to-frame torque dither (RMS of change x270) improved in every bin: 7.9->7.0 at 5-10, 3.55->2.79 at 10-15, 3.18->2.23 at 15-20, 3.37->2.17 at 20-25, 3.01->1.90 at 25+. The measurement low-pass alone accounts for roughly the first half of each reduction; the speed schedule supplies the rest.
