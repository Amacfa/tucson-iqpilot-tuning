# Tucson all-drive steering / warning / fingerprint analysis (2026-09-24)

Device: iq-66480b62, /data/openpilot -> /data/iqpilot, HEAD 0b8c190c (release-candidate, IQ.Pilot 1.0c, clean).
Data: every rlog on the comma, 36 route prefixes, 268 segments, 267 exported (00000002--<redacted>--1 is
truncated on disk: capnp "expected array.size() >= offset + segmentSize" - excluded, ~1 min lost).
Export/analysis code: export_drive_summary.py (ran on the device, bounded memory, one gz per segment,
no VIN/location/raw Params emitted), analyze_drives.py -> analysis.json, plus the ad-hoc fits below.
Nothing on the device was changed; nothing installed.

## 1. Inventory and configuration consistency

* 33 Tucson routes, ~1.43 M CarState frames (~4.0 h recorded), ~2.5 h with lateral control active,
  ~35 min of it at >15 m/s with |lat accel| <= 1 (the torqued-eligible regime).
* Source commits seen: c18bdd63 -> 950be343 -> bf51442c -> 3636baa7 -> ebaa28a1 -> 0b8c190c (current).
  All IQ.Pilot 1.0c, dirty=false. Routes 0000001f..23 are on the current HEAD.
* Every Tucson route ran the same lateral tune: static latAccelFactor 2.9602, friction 0.1087, offset 0,
  steerActuatorDelay 0.1, safetyParam 44, flags 8206, altExp 1024, openpilot longitudinal on,
  IQHkgReducedTorqueFeedback=1 (P x0.8, friction x0.7), IQLateralAccelSlew=1, NN lateral model MOCK.
  => all drives are one tune cluster; cross-route comparisons are valid.
* Live learners never became valid on any route:
  - torqued: calPerc stuck at 40-50 %, valid=false, raw estimates 0.0 on every route. Root cause is
    structural: it needs >=100 points in the |torque| 0.3-0.5 buckets and >=300 in 0.2-0.3 at v>15 m/s and
    |lat accel|<=1. In 2.5 h of driving this car produced 135/821 (left) and 29/668 (right) frames there
    (~6 s / ~30 s at 20 Hz) - the car simply never needs that much torque under 1 m/s^2 (see #3). Static
    params therefore ARE the tune on this car; live learning cannot rescue a bad static value.
  - lagd: status unestimated, validBlocks 0 on every route (needs >50 mph windows with yaw activity).
    Controller falls back to 0.3 s. Offline NCC-lag (desired vs measured curvature, >=0.95 corr windows):
    15-20 m/s 0.29 s (p25/75 0.24/0.36), 20-30 m/s 0.26-0.27 s, 10-15 m/s 0.41 s. The 0.3 s fallback is
    correct for highway speed; no delay change recommended.
  - paramsd: valid, steerRatio 14.8 (CP 13.7), angleOffset ~2.5-2.7 deg, stiffness 1.01.

## 2. Warnings / faults across all drives

* Every route has exactly one steerFaultTemporary flag at t~8 s of segment 0, at standstill, before
  cruise is available and before any LFA frame. That is the boot-time MDPS status sample, not a fault.
* Real in-drive steering faults: route 23 (19 faults, the rejected-LFA arming loop already analysed and
  fixed by the arming candidate), route 13 seg 6 (1, v=4.7 m/s, lat active), route 16 (1, cruise available,
  lat inactive) and route 21 (1, right after a MAIN press with cruise available). The 16/21 cases have the
  same signature as the loop's first fault (fault while application available, native not yet armed) and
  should disappear with the arming candidate; route 13 is a single low-speed event.
* "Steering Assist Temporarily Unavailable" appears only on route 23. "Steer Left/Right" alerts on other
  routes are the lane-change prompts, not faults. cruiseMismatch events (100-1000 frames/route) are the
  known application-vs-native cruise state divergence during MAIN/SET handling - same mechanism family.
* No permanent steering faults, no steerSaturated events, 3 canError on route 0f, 1 on route 19.

## 3. Steering plant: what the car actually does with the torque it is sent

Steady-state frames only (desired and measured lat-accel and steering rate ~constant, no driver torque,
v>8 m/s, 298 k frames), binned by commanded torque (fraction of 270):

| torque | -0.34 | -0.25 | -0.19 | -0.13 | -0.10 | -0.07 | -0.04 | 0.04 | 0.07 | 0.10 | 0.13 | 0.19 | 0.25 | 0.34 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| lat accel m/s^2 | -1.74 | -1.28 | -0.79 | -0.28 | -0.09 | -0.04 | -0.01 | 0.03 | 0.09 | 0.21 | 0.61 | 1.10 | 1.85 | 1.94 |

* Dead band of ~0.10 torque (27 units) where almost nothing happens, then a steep region (~5-7 m/s^2 per
  unit torque between 0.10 and 0.25), flattening above ~0.25. Overall linear fit: 3.29 m/s^2/unit
  (2.9 at 8-12 m/s, 3.3 at 12-16, 4.8 at 16-20). The controller assumes 2.96 everywhere and a friction
  torque of 0.109 x 0.7 = 0.076.
* Consequence visible in the closed loop on every long route: in 0.3-2 m/s^2 curves the feed-forward
  over-commands, the car responds 6-19 % more than requested (|actual|/|desired| 1.06-1.19), and the P
  term runs permanently against the feed-forward (mean P x sign(desired) = -0.14 ... -0.50 m/s^2 while
  F x sign = +0.4 ... +1.6). The I term is near zero (frozen at <5 m/s and on override). Tracking is
  being bought with feedback, which is where "not buttery" comes from: entering a curve the FF overshoots,
  P pulls back, the dead band then lets the wheel relax, P pushes again.
* Tracking error (lat accel RMSE, active, no override): route 22 0.104, route 23 0.118, route 19 0.119,
  route 0f 0.132; p95 ~0.33. Bias essentially zero (left -0.03 / right +0.04).

## 4. Oscillation / smoothness

* No true oscillation left: on 19 highway blocks (>15 m/s, 15 min) 0.5-3 Hz carries 0.3 % of measured
  lat-accel energy and 14 % of torque energy; the 0.2-0.3 Hz peak is road geometry. Teal's reduced-feedback
  change did its job.
* High-frequency dither: commanded torque has 2.2 units RMS frame-to-frame noise, 1.5 units after the EPS
  rate limiter, and the commanded step exceeds the 2-unit/frame limit on 30 % of frames (17 % at the
  output). Source: measurement quantisation (0.1 deg steering angle = 0.027 m/s^2 at 25 m/s) and the
  20 Hz model desired-lat-accel steps (both ~0.01 m/s^2 RMS), amplified mostly by the friction term
  (slope friction*laf/0.2 = 1.13 m/s^2 per m/s^2 of error inside the +-0.2 band - larger than the P gain
  0.64 at 30 m/s) and then P. Amplitude is ~0.6 % of max torque; secondary to #3 for feel.

## 5. Firmware / fingerprint matching

Exact recorded ECUs (identical on every route that ran a fresh query): camera 0x7c4
`NX4 FR_CMR AT USA LHD 1.00 1.00 99211-CW020 14Z`, radar 0x7d0 `NX4__ 1.01 1.00 99110-N9100`,
EPS 0x7d4 `NX4 MDPS C 1.00 1.01 56300-CW000 1A15`.
* In the installed iqdbc fingerprints.py the CW020 camera exists only under HYUNDAI_SANTA_CRUZ_1ST_GEN and
  the N9100 radar only under HYUNDAI_TUCSON_4TH_GEN -> no platform satisfies both -> automatic match fails.
* That is exactly what the logs show: the two routes that started with a fresh FW query after a source
  update (00000000 at c18bdd63, 00000018 at ebaa28a1) fingerprinted as MOCK (18 FW records, no car, no
  control). Routes 16/17 (3636baa7) matched Tucson fuzzily with FW present. All other routes have empty
  carFw: platform forced by the CarPlatformBundle param (currently "HYUNDAI_TUCSON_4TH_GEN, Tucson 2023-24").
* The existing fingerprint candidate (add CW020 to the Tucson camera list) is the right and minimal fix;
  Santa Cruz remains distinguishable by radar. It is still only verified by the offline matcher - a fresh
  ignition-cycle query with CarPlatformBundle cleared is the physical proof, and is only worth doing after
  the candidate DB is installed (otherwise the result is MOCK again, as on routes 0/18).

## 6. Tune candidate (A) - static torque params, no controller code change

File: `.venv/lib/python3.12/site-packages/iqdbc/car/torque_data/params.toml`
(sha256 5753e7d79b23e697b3289378d14cd7f6e25101728d5d9e42086960e6c645c156 on the device)

    -"HYUNDAI_TUCSON_4TH_GEN" = [2.960174, 2.860284, 0.108745]
    +"HYUNDAI_TUCSON_4TH_GEN" = [3.30, 2.860284, 0.120]

* latAccelFactor 2.96 -> 3.30 (+11 %): the all-speed steady-state slope. Cuts feed-forward torque by 10 %
  so P stops fighting FF in 0.3-2 m/s^2 curves (the measured 6-19 % over-response).
* friction 0.109 -> 0.120: applied torque becomes 0.120*0.7 = 0.084 (was 0.076) vs the measured ~0.10 dead
  band; deliberately still below the measurement to avoid adding dither (the friction slope goes
  1.13 -> 1.37 per unit error). Do not go higher without candidate B.
* Not changed: MAX_LAT_ACCEL 2.86 (safety-side clamp), P/I gains, reduced-feedback scaling, slew limiter,
  delay (0.3 s fallback is measured-correct), native limits, F1B (still not installed, not proposed).
* It must be edited in params.toml (not added to override.toml: get_torque_params raises if a platform is
  defined twice). It is picked up at next process start; live torqued still starts its filters from these
  values and will keep reporting calPerc <= 50 %.

Expected effect: lower steady torque in curves (~10 %), P x sign(desired) moving from -0.15..-0.5 toward 0,
|actual|/|desired| toward 1.0, unchanged behaviour on straights. Risk: mild under-steer into curves if the
true gain at the driver's typical 12-16 m/s (3.3) is not representative at 8-12 m/s (2.9) - the I term and
P cover ~0.1 m/s^2 of that; watch for "Steer Left/Right" style corrections at low speed.

Candidate B (not built, needs controller code): first-order low-pass (~50 ms) on the angle-derived
measurement, or a lat-accel dead zone of ~0.03 m/s^2 in get_friction, to remove the quantisation-driven
dither and allow friction closer to the measured 0.10. Only after A has been driven.

Candidate C (out of scope here): NNFF/nonlinear feed-forward reflecting the dead band + steep region. The
data (2.5 h active, 35 min torqued-eligible) is thin for training; revisit after more drives on A.

## 7. Validation status and what replay can / cannot prove

* Offline replay cannot validate a tune on this car: the plant is the EPS + vehicle, and closed-loop
  drive data does not identify it well enough to simulate (FIR identification smears over 1.5 s,
  R^2 0.76). Candidate A's justification is the steady-state plant measurement above, not a simulation.
* Physical A/B protocol (supervised, ordinary roads, driver hands ready, no highway yanks):
  1. Install arming candidate (already software-validated) and candidate A together while parked;
     normal restart; parked ignition-on check.
  2. Drive the same 15-20 m/s loop as route 22/23 twice (baseline logs exist for comparison).
  3. Re-run export_drive_summary.py + analyze_drives.py on the new routes and compare against routes
     22/23: tracking RMSE, |actual|/|desired| by lat-accel bin, mean P x sign(desired), torque HF RMS,
     rate-limited fraction, steer override rate, fault count (should be 1 boot sample, 0 in drive).
  4. Only then consider B.

## 8. Limitations

* One truncated segment excluded. Route durations in analysis.json 'dur_s' are per-segment maxima
  (capped ~599 s); use segments x 60 s for route length.
* Lateral accel "actual" is the controller's own angle-based measurement (no yaw-rate signal from this
  car), so the tune is self-consistent with what the controller sees, not an independent IMU truth.
* Speed coverage is mostly 8-20 m/s; the >22 m/s conclusions rest on ~5 min of data.
