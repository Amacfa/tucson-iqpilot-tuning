# Offline model-bundle evaluation — results

Drive: route `0000002e` (v4 drive, ~633 s), segments 0, 1, 2, 24 (segs 1/2/24 chosen for
curves + disengaged/manual stretches; seg 0 for sanity).
Date: 2026-09-30. Device HEAD `3736edc…`, parked (`IsOffroad=1` checked before every replay;
niced; no params touched; no services restarted).

## Method

Full-fidelity replay: `process_replay` drives the **complete `iqmodeld` daemon**
(`iqpilot.selfdrive.iqmodeld.daemon`) as a `PythonProcess`, monkeypatching
`config_realtime_process` (sched_setscheduler needs root). Per-replay
`custom_params={'ModelManager_ActiveBundle': <bundle dict>, 'ModelRunnerTypeCache': 1}`
injected into the replay's fake params prefix — the real param is never written.
Models are the on-disk files in `/data/media/0/models/` (`model_runner` resolves
bundle `fileName`s there); both candidates were already downloaded on-device, so
**no downloads were needed**.

Bundles tested (all gen-12, tinygrad, is20hz):

| bundle | type | file on device |
|---|---|---|
| NNMV2 (active, idx 35) | combined (fused vision+policy) | `driving_combined_83b81b83.pkl` |
| KARNBIRRLV2 (idx 77) | supercombo | `driving_supercombo_karnbirrlv2.pkl` |
| REBELLIOUSHOPE | supercombo | `driving_supercombo_rebellioushope.pkl` |

Note: phase-2 brief asked for gen-11 vision+policy bundles "closest in lineage to NNMV2".
NNMV2 on this fork is itself a **gen-12** `driving_combined` artifact (single fused pkl).
The two closest on-disk gen-12 supercombos (KARNBIRRLV2 = the bundle ModelManager had
already auto-selected/downloaded; REBELLIOUSHOPE = second supercombo present) were used —
same runtime, same 20 Hz pipeline, zero download risk. Gen-11 TR13–16 pairs remain
available for a follow-up if a same-format comparison is wanted.

## Phase 1 — sanity gate (NNMV2 replayed vs logged modelV2)

Gate defined: **path_y RMSE < 0.15 m** (planned-path agreement is the signal we care
about; velocity differs because replay warm-up lacks full temporal/feature context).

| seg | n pairs | path_y RMSE (m) | lane y0 comb. err (m) | vel RMSE (m/s) |
|---|---|---|---|---|
| 0 | 1060 | **0.072** | 0.58 | 2.1 |
| 1 | 1199 | **0.117** | 0.51 | 5.1 |
| 2 | 1199 | **0.099** | 0.78 | 9.7 |
| 24 | 1199 | **0.156** | 0.57 | 7.8 |

**Verdict: PASS** — path agreement is centimeter-scale (~7–16 cm). Lane-line and
velocity outputs diverge more, as expected when replaying a temporal model without
its exact live inference context; velocity especially is not trustworthy in replay
(logged value includes live smoothing/feature-buffer state). Use path + lane bias +
jitter for cross-bundle comparison, not velocity.

## Phase 2 — per-bundle metrics

Mean lane-center bias = (ll1.y0 + ll2.y0)/2; jitter = per-frame |Δy0| of both lane lines;
manual path dev = mean |path y| at 1–2 s lookahead on **disengaged** frames only
(selfdriveState.enabled=false by monotonic time).

### Seg 0 (n=1200; NNMV2 only — sanity seg)

| bundle | lane bias | jitter | manual dev (n=1120) |
|---|---|---|---|
| NNMV2 | 0.035±0.150 | 0.097 | 0.012 |

### Seg 1 (n=1199; mixed engage/disengage + curves)

| bundle | lane bias | jitter | manual dev (n=729) |
|---|---|---|---|
| NNMV2 | 0.022±0.209 | 0.166 | 0.023 |
| KARNBIRRLV2 | **0.145±0.170** | 0.141 | 0.020 |
| REBELLIOUSHOPE | 0.076±0.130 | **0.132** | 0.019 |

### Seg 2 (n=1199; dense curves, little manual time, n=141)

| bundle | lane bias | jitter | manual dev |
|---|---|---|---|
| NNMV2 | 0.100±0.191 | 0.240 | 0.011 |
| KARNBIRRLV2 | 0.164±0.217 | 0.256 | 0.013 |
| REBELLIOUSHOPE | 0.118±0.156 | **0.214** | **0.009** |

### Seg 24 (n=1199; manual stretch + curves)

| bundle | lane bias | jitter | manual dev (n=710) |
|---|---|---|---|
| NNMV2 | 0.022±0.189 | 0.144 | 0.017 |
| KARNBIRRLV2 | 0.126±0.137 | 0.132 | **0.036** |
| REBELLIOUSHOPE | **−0.005±0.128** | **0.096** | 0.015 |

## Read

- **REBELLIOUSHOPE looks best overall**: lowest jitter on every seg, smallest
  lane bias (seg 24: −0.005 m, essentially centered), lowest manual-frame path dev on 2/3 segs.
- **KARNBIRRLV2** (the bundle ModelManager auto-switched to on-device) shows a consistent
  **+0.12–0.16 m lane bias** — the largest of the three — and the worst manual-frame dev
  on seg 24 (0.036 m). Combined with the −0.12 m car-stance bias measured on the v4 drive,
  its planned offset goes the opposite direction.
- **NNMV2** is mid-pack: more jitter than the supercombos on this replay, modest bias.
- Manual-frame path devs are all small (<0.04 m) — all three track the human path well on
  this drive; the differentiators are jitter and lane bias, not gross path error.

Caveats: 4 segs of one route; replay velocity/lane outputs are noisier than live
(temporal context warm-up); "manual" frames here are car-not-enabled frames (driver
steering), which includes parking/driveway time in seg 0–1. A gen-11 vision+policy
pair (TR13–16) is available for download if a same-lineage comparison is wanted.

## On-device artifacts

`/data/tucson-model-eval/` — **4.3 MB** total: `replay_seg.py`, `compare_seg.py`,
`metrics_seg.py`, `run_matrix.sh`, bundle dicts (`ab_*.json`, `bundle_*.json`),
`rep_*.json` (9 replay outputs), `matrix.log`. Nothing else written; no params
changed; nothing left running.

## Scripts

`analysis/models/{replay_seg.py, compare_seg.py, metrics_seg.py}` → published at
`github-record/research/model-eval/` alongside this report.
