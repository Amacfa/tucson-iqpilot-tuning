# Offline model-bundle evaluation — feasibility study (3736edc, read-only)

Question: can we run alternative driving models over recorded drives and compare
plans without touching the live stack? **Verdict: feasible, on-device, ~4–8 h of
harness work for the first comparison.** Details below.

## 1. ModelManager mechanics

- `ModelManager_ModelsCache` param holds a **94-bundle catalog** (indices 0–93)
  with per-bundle `short_name`, `display_name`, `is_20hz`, `generation`, and per-model
  `artifact.downloadUri`/`fileName`. `ModelManager_ActiveBundle` = **index 35, NNMV2
  ("North Nevada Model V2")**.
- Catalog shape (three families): `vision`+`policy` pairs (gen 10–11, e.g. TR13–TR16,
  KD, LD, SGO), single `supercombo` (gen 3–5 + gen 12 DRLV/AT/CHLR…), and gen-12
  IQModels (NovaSpectra, NanchoKoukamonga, Strevala, NovaScala, NovaSpark).
- **On disk**: only the shipped default — `/data/iqpilot/iqpilot/selfdrive/iqmodeld/default_model/`
  = `driving_vision_c210m_tinygrad.pkl` (62.6 MB) + `driving_policy_c210m_tinygrad.pkl`
  (14.6 MB) + `bundle.json`. **No alternative bundle is downloaded** — a target
  bundle must be fetched once via its `downloadUri` (`model_bundle_downloader.py`
  exists; needs internet through the normal device path or a manual fetch + hash check).
- Selection: `iqmodeld/models/helpers.py get_active_bundle()` reads
  `ModelManager_ActiveBundle` and resolves artifact files under the model root —
  a replay runner can bypass this by instantiating the bundle/artifacts directly
  (the param does not need to change).

## 2. Replay path

- `iqpilot/selfdrive/test/process_replay/model_replay.py` exists — replays modeld
  over logged `roadCameraState`/`roadEncodeIdx` + decoded camera frames via
  `FrameReader` and `replay_process` (msgq pub/sub subprocess).
- **Inputs present**: every segment of routes 2d/2e has `rlog.zst` (contains
  `roadCameraState` ~1200/seg, `roadEncodeIdx` ~1200/seg, `extrinsicsCalibration`,
  `carParams`, `carState`, `carControl`) plus `fcamera.hevc` (~36 MB/min-seg),
  `qcamera.ts` (~19 MB), `ecamera.hevc`, `dcamera.hevc`.
- **Decode**: `/usr/local/bin/ffmpeg` on device; `FrameReader` handles hevc.
- **Compute**: `tinygrad` installed in the venv, `Device.DEFAULT = QCOM`,
  `/dev/kgsl-3d0` + `/dev/dri/renderD128` present — GPU inference runs on the comma
  while parked (iqmodeld only runs onroad, so GPU/msgq are free; still run at
  reduced load, not while charging-limited). Off-device (Mac/x86) is impractical:
  the pkls are tinygrad/QCOM-targeted aarch64 artifacts.
- **Non-active bundle**: the runner needs explicit artifact paths; `get_active_bundle`
  is only the *default* resolver — nothing forces it. Risk: gen-12 supercombo
  bundles may need different input plumbing than the gen-11 vision+policy pair
  (`modeld_selector`/`egpu_*` machinery suggests NNMV2 is run via a split pipeline);
  first target should be a same-generation vision+policy bundle to reuse the
  NNMV2 runtime verbatim.

## 3. Proposed evaluation protocol

For each candidate bundle, replay segments of routes 2d/2e (and a v2 route for
variety), capturing published `modelV2`/`drivingModelData` output:

1. **Self-consistency sanity**: replay NNMV2 itself on one segment; compare its
   `modelV2` output to the logged `modelV2` (position/laneLines/desiredCurvature)
   — validates the harness before trusting any comparison.
2. **Human-path agreement**: on `selfdriveState.enabled=False` (or
   `steeringPressed=True`) windows, compare plan `position.y`/curvature to the
   human-driven path (from `carState` + `livePose`/`cameraOdometry` trajectory):
   lateral deviation of the plan from what the human actually did.
3. **Lane-line consistency/jitter**: frame-to-frame Δ of `laneLines[i].y[0]` and
   lane-width estimate; jitter RMS per bundle (lower = stabler perception).
4. **Desired-curvature smoothness**: `meta.desireState`/plan curvature derivative
   — jerk proxy on straight vs curve windows; compare to the NNMV2 reference.
5. **Speed-plan sanity** (e2e-relevant if ExperimentalMode ever re-enabled):
   `action.desiredAcceleration` vs road speed.

## Verdict

**Feasible — yes, on-device.** Needed: (a) download 1–2 candidate bundles via
their `downloadUri` (~100–300 MB, one-time), (b) a thin runner that instantiates
the model runtime with explicit artifacts and replays `fcamera.hevc` + rlog
messages — reuse `model_replay.py`/`process_replay` machinery rather than writing
new, (c) the NNMV2 self-consistency pass first. **Estimate ~4–8 h** for the first
bundle comparison; ~1 h per additional bundle. Constraints: run parked/idle only
(GPU shared with nothing while offroad, but keep load modest), ~1.2 GB of fcamera
per 33-seg route stays on /data (30 GB free).
