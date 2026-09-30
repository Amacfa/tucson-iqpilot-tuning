# Lane-position bias + lateral-offset code survey (release 3736edc)

Analysis only — nothing installed, nothing restarted on the comma.

## Method

Parsed `modelV2` messages from **rlogs** (~18 Hz) on device, filtered to:
`selfdriveState.enabled && carControl.latActive && !steeringPressed && vEgo>5`
and `laneLineProbs[1] > 0.5 && laneLineProbs[2] > 0.5`.

- Signed offset = `(laneLines[1].y[0] + laneLines[2].y[0]) / 2` (lane center in car frame at x≈0).
- **Sign convention (verified on-device)**: `laneLines[1]` (left line) y[0] ≈ −1.8 m, `laneLines[2]` (right line) y[0] ≈ +1.5 m → **negative y = left**. So a **negative offset = lane center to the car's left = car sitting RIGHT of lane center**.
- Lane width = `laneLines[2].y[0] − laneLines[1].y[0]` (reported |width| ≈ 3.0–3.2 m).
- Path offset = `modelV2.position.y` at x ≈ 15 m and ≈ 25 m (y[0] is identically 0 — the plan passes through the ego origin, so x=0 cannot discriminate; forward samples are used instead).
- Groups: **v4** = route `2e` (33 segs, tune-v4), **v3h1d1** = route `2d` (tune-v3+H1+D1), **v2** = routes `25`/`28` (tune-v2 era). No v5-era drive exists yet (installed after the last drive).

## Results — offset from lane center (metres; − = car right of centre)

| group | n | mean | median | std | median lane width |
|---|---|---|---|---|---|
| v4 | 5079 | **−0.120** | **−0.098** | 0.265 | 3.16 |
| v3h1d1 | 1720 | +0.047 | −0.005 | 0.223 | 2.96 |
| v2 | 7185 | +0.017 | +0.038 | 0.238 | 3.16 |

### By speed (median offset / median path-y@15m)

| speed (m/s) | v4 | v3h1d1 | v2 |
|---|---|---|---|
| 5–10 | −0.010 | −0.030 | −0.006 |
| 10–15 | −0.079 | +0.004 | +0.014 |
| 15–20 | −0.134 | (n<100) | +0.047 |
| 20–30 | (n<100) | — | +0.069 |

### By lane width (median offset, split at group median width)

| group | narrower lanes | wider lanes |
|---|---|---|
| v4 | −0.110 | −0.086 |
| v3h1d1 | −0.010 | +0.004 |
| v2 | +0.065 | +0.003 |

### Planned path ahead (modelV2.position.y; + = to the right)

| group | med @15 m | mean @15 m | med @25 m | mean @25 m |
|---|---|---|---|---|
| v4 | +0.014 | +0.036 | **+0.040** | **+0.098** |
| v3h1d1 | −0.001 | +0.022 | +0.005 | +0.055 |
| v2 | −0.007 | −0.012 | −0.017 | −0.034 |

## Interpretation

- **v4 drive: the car cruised ~10 cm RIGHT of lane centre** (median −0.098), and the bias grows with speed (−0.01 at 5–10 → −0.134 at 15–20 m/s) and is slightly worse in narrower lanes (−0.110 vs −0.086). v3h1d1 was centred; v2 sat a few cm LEFT of centre — i.e. the stance moved rightward over time/routes.
- **Path bias vs control bias**: the planned path does not pull back toward lane centre — on v4 the path at 25 m is ~+0.04–0.10 m to the *right* of the car, same side as the car's right-of-centre stance. If the controller were at fault (car left of a centred plan), the model path would curve toward centre (negative y). Instead the plan extends the rightward offset → **this is a planned (model/calibration) offset, not a lateral-control tracking error**. In v2, where the car sat left of centre, the path samples were correspondingly negative — again the plan matches the stance rather than correcting it. This is consistent with how these models consume lane geometry (the network plans relative to where it perceives the lane), so a small perception/calibration asymmetry shows up as a steady offset, not a control error.
- Caveats: groups are different routes (road camber/route mix differ — v2's leftward stance could partly be road crown); std ≈ 0.24 m dominates the mean, so the effect is small (~4% of lane width); `position.y[0]` ≡ 0 by construction.

## Calibration (liveCalibration service absent; `extrinsicsCalibration` used)

| group | calStatus | calPerc | rpyCalib [roll?, pitch, yaw] (rad) | height |
|---|---|---|---|---|
| v4 | calibrated | 100 | [−1.8e-5, +0.0366, −0.0241] | 1.32 |
| v3h1d1 | calibrated | 100 | [+1.3e-5, +0.0369, −0.0232] | — |
| v2 | calibrated | 100 | [−3.2e-5, +0.0391, −0.0244] | — |

Rpy is stable across all eras (calPerc 100, `calibrated`) — no drift event; the v4 rightward stance is not explained by a calibration jump.

## Code survey — lateral offset & model selection (3736edc)

**Lateral offset:**
- **`CameraOffset` param: current value on device = `0.0`** (default "0.0", PERSISTENT, in `params_keys.h`). This is the only live lateral-offset knob.
- Applied at **`iqpilot/selfdrive/modeld(→iqmodeld)/daemon.py:609`**: `self._warps.set_offset(Params.get("CameraOffset", 0.0))` → `camera.py CameraOffsetHelper`, which applies a **sheared camera-projection transform to the model input** (smoothed via `_OffsetSmoother`). I.e. it warps what the model *sees*, indirectly shifting the planned path — it is NOT a `PATH_OFFSET`-style post-hoc lateral bias. There is **no PATH_OFFSET / LaneChangeOffset / camera_offset in lateral_planner/drive_helpers**; the lateral planner gets the path already biased.
- `ldw.py` has a literal `CAMERA_OFFSET = 0.04` constant — **LDW alert logic only**, does not touch steering or the plan.
- Related model-side params present on device: `ModelLatSmoothSec`, `PlanplusControl` (not surveyed in depth — path smoothing/plan blending, not a static offset).

**Model selector:** yes — bundle-based, not a simple model-name param:
- `ModelManager_ActiveBundle = {"index":35,"internalName":"NNMV2",…}` (active driving model), plus `ModelRunnerTypeCache=1`.
- `IQEmacEnabled` / `egpu_selected` backend toggle and `IQEmacSmallModel=0` in `iqmodeld/daemon.py`; NNFF remains off (`NeuralNetworkFeedForward` absent, no models-dir content).

## Bottom line

The v4 drive shows a small, speed-growing **~10 cm right-of-lane-centre stance** that the model itself plans (path samples extend the same direction) — i.e. a **planned/perception offset, not control error**. The only device knob is `CameraOffset` (currently 0.0, applied as an input-camera warp in iqmodeld). If the user wants to counter a right-of-centre stance, a small *negative* `CameraOffset` (sign convention: verify by a small trial, e.g. ±0.02 — the warp direction needs an on-road check) would shift perceived lane geometry. Recommend measuring again on the next (v5) drive before changing anything — single-route, single-drive evidence.
