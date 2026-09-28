# Drive-1 sim inputs (route 00000024--f0646026ab, post-install 3736edc)

## A. /home/ubuntu/tucson/analysis/wobble/drive1_frames.npz
16,506 lat-active rows. Arrays: t, seg(0-4), vEgo, aEgo, dla (desired latAccel setpoint),
ala (measured latAccel = controlsState.torqueState.actualLateralAccel = curvature*v^2),
ang (steeringAngleDeg), rate (steeringRateDeg), dtq (carState.steeringTorque = driver torque),
dtqe also available in source, prs (steeringPressed), tq (carControl.actuators.torque cmd),
tqo (carOutput torque, rate-limited), p, i, f, out (torqueState.output), act, err, sat,
yaw (carState.yawRate), ldel (lateralDelay interpolated to 0.1s grid, NaN where not
published that frame ~60%), laf (latAccelFactorFiltered), fr (frictionCoefficientFiltered).
UNAVAILABLE: roll (no liveCalibration/liveParameters services in rlog), measured
latAccel raw steering-angle path (ala IS the curvature*v^2 measurement - same thing),
driver-requested vs EPS torque split beyond dtq/dtqe.

## B. torque->latAccel gain fits (slope = effective latAccelFactor; negative sign = convention)
### drive 1 (friction 0.12, learned reset tbk=0)
bin@delay     slope    R2     n
3-5  @0.1s   -1.894  0.735  756
3-5  @0.2    -1.910  0.761  746
3-5  @0.3    -1.904  0.773  736
5-8  @0.1    -1.520  0.745  819
5-8  @0.2    -1.423  0.655  809
5-8  @0.3    -1.320  0.563  799
8-12 @0.1    -1.872  0.321  3139
8-12 @0.2    -1.901  0.330  3129
8-12 @0.3    -1.693  0.260  3119
12-16@0.1    -2.046  0.571  962
12-16@0.2    -1.312  0.237  952
12-16@0.3    +0.579  0.047  942   (fit degrades - delay misspecification)

### baseline (all pre-install segs)
3-5  @0.1    -1.488  0.591  25923
5-8  @0.1    -2.411  0.737  42794
8-12 @0.1    -3.342  0.738  56675
12-16@0.1    -4.294  0.664  83592
(0.2/0.3s delays nearly identical, slightly lower slope)

### baseline learned-only (totalBucketPoints>1000; ~97% of frames)
3-5  @0.1    -1.531  0.590  23256
5-8  @0.1    -2.373  0.737  40056
8-12 @0.1    -3.186  0.777  52166
12-16@0.1    -4.312  0.655  79537

liveTorqueParameters: baseline every seg lafFiltered=2.96017 (friction filtered 0.10875
pre-tune); drive 1 lafFiltered=2.9602, frFiltered=0.12, tbk=0.0, calPerc=0, valid=0
constant all drive (params fallback, learner empty after update).

## C. lateralDelay
Drive 1: published ~4.8 Hz (207 msgs/seg), CONSTANT 0.300 s for every frame of all 5 segs
(vs CarParams steerActuatorDelay=0.1). Value matches device param IQSteerDelayCache=
0.30000001192092896 — appears to be a cached/estimated steer delay at 0.3, published
flat; SteerShortfallCheck consumes it at clamps (0.1,1.0). No lateralDelay msgs in
pre-457 exports (service didn't exist / not logged then).

## D. IQ params matching filter (name=value, reader sites)
AolPauseOnSteeringOverride=0 -> iqpilot/sab/behavior.py:51 (pause-lateral-on-override)
AolSteeringMode=0 -> iqpilot/selfdrive/car/interfaces.py:95 (stores 2), ui steering.py:21-31
CustomSteerMax=0 / CustomSteerDeltaUp=0 / CustomSteerDeltaDown=0 /
CustomSteerDeltaUpLC=0 / CustomSteerDeltaDownLC=0
  -> artifacts iqdbc car/hyundai/carcontroller.py:209-213 (steer limits/deltas; 0=stock)
EnableCurvatureController=1 (default-applied flag set) -> manager.py:46-48 (VW-only car branch)
EnableSmoothSteer=0 -> controlsd.py:111-113,153 (curvature-car only; not Hyundai)
IQHkgReducedTorqueFeedback=1 -> latcontrol_torque.py:514 (kp scale 0.8)
IQLateralAccelSlew=1 -> latcontrol_torque.py:527 (slew limiter enabled)
IQLatJerkGain=1.0 -> latcontrol_torque.py:272 (NNFF/jerk gain)
IQLiveSteerDelay=1 -> iqpilot/common/steer_delay.py (live delay vs fixed)
IQSoftwareSteerDelay=0.2 / IQSteerDelayCache=0.300 -> steer_delay.py:13-18
IQSteerEffortArc=1 -> UI only (mici visuals)
IQTeslaTorqueBlend=0 -> iqdbc lvbs interfaces.py:93 (VW brand only)
IQDynamicConditionalCurves=1 -> iq_dynamic/imahelper.py:8
IQLateralCurvatureLookahead=0 -> controlsd.py:81 (disabled)
LatSmoothSec=13 (not read in iqpilot controls; likely legacy/nav)
ModelLatSmoothSec=0, ModelSmoothingEnabled=0 -> iqmodeld/daemon.py:94-97
IQBlinkerMinLateralSpeed=20, IQBlinkerPauseLateral=0 -> blinker_pause.py:11-13
IQLaneTurnDesire=0, IQLaneTurnValue=19.0 -> helpers/lane_turn.py:62-63
LaneLineCheck=0 -> hyundaicanfd.py:753 (ccnc lane-line check)
LaneChangeNeedTorque=0 -> no code hits (dead param)
LaneChangeBsd=0, LaneChangeContinuous=0, LaneChangeDelay=0.0, NavExitLaneChange=1,
  IQLaneChangeBsmDelay=1, IQLaneChangeTimer=0 -> lane-change logic
iqMqbSteeringLockout=0 -> UI only (VW)
LiveTorqueParameters=<binary blob> (learned state, tbk=0 post-update)
