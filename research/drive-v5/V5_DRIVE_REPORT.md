# V5 drive report — tune-v5 (FF refit 12–25) + KARNBIRRLV2 + new settings

Drives: `0000002f` (12 segs), `00000032` (8 segs); `00000030` = failed-boot attempt
(see ENGAGE_FAILURES.md). Device: latcontrol `db166b61` (v5), controlsd `bbfa1b6e` (D1),
carcontroller `a8cf776c` (v2), hyundaicanfd `cfd69418` (LFA-AB v0). Active model:
**KARNBIRRLV2** (index 77 — auto-selected by models_manager, left as-is per user).
Settings: ExperimentalMode=off, LongitudinalPersonality=1 (but see drift note),
LongIncrements=on, LaneChangeBsd=on.

## Engage failures — headline

CAN-invalid window at boot + `selfdrivedLagging`/`commIssue`/`posenetInvalid`
during init; route 30 never got CAN stable within its segment → couldn't engage;
resolved by the user's comma+car restart (route 32 boot settles in ~9 s, brief
steerTempUnavailable at 14–17 s, then normal). **No steer faults, no thermal/disk
issue, model execution healthy (0% frame drops). Not a model-load problem — a
boot-time CAN/comms settle issue.** Full detail: `../faults/ENGAGE_FAILURES.md`.

## Steering quick-check (same detectors as v4 report)

**Tracking by speed (undelayed ref, unpressed, unsaturated, steady phase):**

| v bin | v4 tr | v5 tr | n (v5) |
|---|---|---|---|
| 10 mid | — | 1.20 | 81 |
| 12 mid | 1.176 → predicted 1.09 | **0.99** | 237 |
| 13 mid | 1.188 | **1.22** | 78 |
| 14 mid | 1.137 | **1.11** | 62 |
| 15 mid | 1.186 | **1.12** | 517 |
| 16 mid | — | **1.08** | 565 |
| 17 mid | — | 1.21 | 623 |

The 12 m/s bin landed almost exactly on the open-loop prediction (0.99 vs ~1.09 —
actually *below*, meaning the P/I absorption caveat was real). 13/15/17 sit at
1.12–1.21 — mild residual FF over-scale, similar to v4 at those bins; the signed-p
still negative (−0.1…−0.2) → feedback trimming an over-produced FF as before.
**No new pathology introduced; modest improvement centered on the retuned range.**

**Low speed (v5 kp_scale floor unchanged 0.7):** 5–7 m/s steady tr 0.85–1.09 mixed —
same mild under-response as v4 at 5–7 m/s, as designed (P untouched).

**Wobble:** sub-threshold hunt (1–3 s windows, 1.0–2.5 Hz, ~0.5× amplitude) over
routes 2f/30/32: **zero candidates**. No P-mode episodes at all on the v5 stack.

**Lane-center bias under KARNBIRRLV2** (modelV2 laneLines, engaged+unpressed+v>5,
probs>0.5 — same method as LANE_OFFSET.md):
mean **−0.029 m**, median **+0.022**, std 0.248 (n=3342) — vs v4/NNMV2's **−0.120 m
mean**. The rightward stance is **gone** under the supercombo; consistent with the
model-eval finding that NNMV2 plans ~+0.02–0.10 right while KARNBIRRLV2 plans left.
Calibration unchanged (calPerc 100, rpy ≈ prior) → this is a model difference, not cal.

## Longitudinal (v2 stack, ExperimentalMode now OFF)

| metric | v4 (e2e on) | v5 drives |
|---|---|---|
| capped share (set−v>3, no lead, \|a\|<0.3) | **0.33** (median gap 4.12 m/s) | **0.019** route 32 (median gap 0.51); 0.0 route 2f* |
| stale-set engages (min_acco_6s < −0.5) | several/drive | 2 on route 32 (t=84.6 gap−2.46; t=117.3 gap−3.44) |
| launches | 3/route, a_pk ~2.4 | 1 launch route 2f (a_pk1s 0.22, cmd 0.66 — gentle) |
| gas overrides | 12/drive | 643 frames 2f + 434 frames 32 (fewer than v4 rate) |

*route 2f median gap 5.49 m/s reflects higher set speed with active accel — the
"capped share" (gap AND flat accel AND no lead) is 0, i.e. it was climbing, not stuck.

**Verdict: ExperimentalMode=off fixed the won't-climb complaint** — cruise-source
accel now chases set speed; capped-frame share fell 0.33→0.019.

## Drift / housekeeping flags

- **`LongitudinalPersonality` reads 2 again** (applied 1) — flagged by hourly
  param_drift. Either user touched the UI or a setting reset occurred; needs
  re-apply or user confirmation.
- Route `00000031` rlogs truncated on device (2 segs unrecoverable) — recorded,
  not retried.
- `active_model` hourly check live: KARNBIRRLV2(77), no warnings.
