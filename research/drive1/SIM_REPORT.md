# Drive-1 curve-exit closed-loop sim (offline, 3736edc, tune v1 installed during drive)

Script: `sim_curve_exit.py` on `drive1_frames.npz` (16,506 lat-active frames, 100 Hz).
Plant: first-order lag + delay fitted to drive 1 (grid T/tau, per-speed-bin gain by least squares).
Controller: mirror of IQ LatControlTorque (speed-scheduled KP x0.8 reduced-feedback, KI 0.15,
FF + friction 0.12 x0.7, torque = latAccel/latAccelFactor, Hyundai 2-up/3-down rate limit at 270).
Metric: 0.5-3 Hz energy fraction of torque / latAccel in the 3 s after a curve exit (5 clean exits,
speeds 13.1/10.6/11.0/4.8/4.9 m/s).

## Plant fit
T=0.6 s (grid edge), tau=0, K by bin: 3-6: 2.10, 6-9: 3.03, 9-13: 3.58, 13-18: 2.69 m/s^2 per unit torque.
Drive-1 effective gains are ~40% lower than the pre-install baseline (8-12 m/s: 1.9 vs 3.3 via delayed
regression) - the torque the controller commanded was not fully turning into lateral motion, i.e. part
of the command was high-frequency content the EPS/chassis filters out. That is what the wobble is.

## Variants (mean over 5 exits)
| variant | torque band frac | latAccel band frac | dither x270 |
|---|---|---|---|
| v1 (60 ms measurement filter) | 0.672 | 0.401 | 2.44 |
| v2 (no filter) - INSTALLED NOW | 0.634 | 0.383 | 2.38 |
| v2 + 30 ms filter | 0.655 | 0.391 | 2.41 |
| v2 + low-speed KP x0.6 (<10 m/s) | 0.618 | 0.375 | 2.28 |
| v2 + low-speed latAccelFactor from fit | 0.636 | 0.385 | 2.43 |
| v2, controller delay 0.3 s (as actually used) | 0.567 | 0.365 | 2.69 |
| logged drive 1 (real) | 0.828 | 0.763 | - |

## Reading
- Direction: filter out (v2) is better than v1 in every metric; a 30 ms filter is in between. Consistent
  with the lag hypothesis, so v2 is the right thing to A/B on drive 2.
- Magnitude: the linear model reproduces ~0.63 vs 0.83 logged and only 0.38 vs 0.76 in latAccel, so it
  under-predicts the real wobble. Something the model lacks (EPS internal dynamics, 0.1 deg steering
  quantization at 5 m/s, driver hand load - 10-16% of frames had steer pressed) carries a large part of
  the oscillation. Do not over-trust the 4-6% deltas; treat the sim as directional.
- Next candidate if drive 2 still wobbles: low-speed KP x0.6 below 10 m/s (IQ's KP schedule is 11.5 at
  5 m/s vs 0.8 at 30 m/s - the P term hit 2.4 m/s^2 at the worst exit). Not installed.
- Controller delay: setpoint is desired latAccel delayed by lateralDelay = 0.300 s in BOTH baseline and
  drive 1 (cross-correlation r>0.999). That is lagd's initial value (steerActuatorDelay 0.1 + 0.2), stored
  in the LiveDelay param and never re-learned (0 valid blocks). Not an update artifact; a candidate for
  later investigation (measure the real actuator delay from step-like inputs), not for drive 2.
- Torque learner (lateralTorqueParameters) is empty since the update (0 bucket points); latAccelFactor
  comes from the speed table, friction 0.12 from params. It will refill over normal driving.
