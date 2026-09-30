# Engage-failure / "bunch of errors" investigation — v5 drive set (2026-09-30)

Scope: routes `0000002f` (12 segs, rlog mtime 16:13Z), `00000030` (1 seg, 18:06Z),
`00000032` (8 segs, 18:14Z). Route `00000031` has only 2 partial dirs whose rlogs
failed to pull (`export failed` — truncated). Read-only analysis; nothing changed.

## Timeline reconstruction

| route | window | what happened |
|---|---|---|
| 2f seg 0 | first ~8 s of route | CAN invalid t−0→7.6 s, commIssue ×8, posenetInvalid, paramsdTemporaryError — **normal boot settle**, then enabled at ~51 s and drove fine for 12 segs |
| 30 seg 0 | whole route (~9.6 s of log) | **never initialized**: selfdriveInitializing loop + canError ×3 + commIssue + selfdrivedLagging + posenetInvalid + paramsdTemporaryError for the entire recorded segment; `enabled` never went true. Only 28 modelV2 msgs total. |
| 31 | — | drive attempted but rlogs truncated (can't pull) — likely part of the same bad state |
| 32 seg 0 | first ~29 s | CAN invalid t−0→8.3 s, commIssue, posenetInvalid, paramsdTemporaryError, **buttonEnable pressed at t+12.6** (couldn't latch — CAN just recovered), steerTempUnavailable t+14.4 & 17.2, steerOverride 16.7, enabled briefly 12.6→13.8 s then disabled, overriding 29.1 s, then drove fine for 8 segs |

## Evidence (facts)

- `canValid=False` frames: 2f/0 → 19 (t≤7.6 s), 30/0 → 79 (throughout the short segment), 32/0 → 112 (t≤8.4 s, none after), 32/7 → 3 stray. **CAN-validity windows are concentrated at boot** and clear within ~8–9 s on healthy boots.
- `pandaState` is **not logged in this fork's rlog** at all (0 msgs in every seg) — panda internals not observable from logs.
- Model health is clean everywhere it ran: `frameDropPerc = 0.0` on all frames; `modelExecutionTime` ~0.03 s typical, max 1.79 s (single warm-up frame in the failed boot). `selfdrivedLagging` appeared **only** in route 30 (and at boot of 2f/32 while services spun up) — never during driving.
- `deviceState` on route 30: thermal `green`, cpu ~50–58 °C, mem 76%, freeSpace ~31% — no thermal/disk/memory cause.
- No `steerFaultTemporary/Permanent` anywhere; `steerTempUnavailable` fired twice in 32/0 during the CAN-invalid/just-recovered window (t+14.4, t+17.2) — transient.
- Errors that resolved "after restarting comma and car" = route 30 is the failed-boot attempt; route 32 is the first drive after the restart (boot-settle alerts again visible, cleared by t≈9 s, brief enabled blip at 12.6 s then normal).

## Ranked mechanisms

1. **CAN-bus not ready at boot (canValid=False + canError + commIssue)** — *verified by logs*: in every route-0 the CAN stream is invalid for the first ~8 s, and in route 30 it apparently never fully settled (canError still firing at the last logged frame, selfdrivedLagging active). Until CAN is valid, `selfdriveInitializing` blocks engagement — this is exactly the "couldn't engage + bunch of errors" the user saw on the instrumented boot. A flaky CAN/panda link during startup is the primary suspect; on route 32 the same alerts cleared in ~9 s and engagement worked.
2. **Process init lag (posenetInvalid + paramsdTemporaryError + selfdrivedLagging)** — *verified present*; these are downstream of the same startup window (calibration/localizer not yet fed). In 2f/32 they cleared on their own; in 30 they did not within the segment. Contributor, not root cause.
3. **KARNBIRRLV2 model load/lag** — **no supporting evidence**: modelV2 exec ~30 ms steady, zero frame drops, alerts are CAN/comms-flavored not model-flavored. The model-switch coincided in date only; the failure mode (canError/commIssue) is a hardware-comms signature, not an inference one. Listed as unlikely.
4. **Thermal/disk/memory** — ruled out: green thermal, 31% free, mem 76% during the failure.

## Note on `selfdrivedLagging` in route 30

selfdrived's lag alert plus persistent commIssue in a ~10 s window suggests the failed
boot had service-level stalls beyond CAN warm-up (possibly the heavy `models_manager`
download/write of `driving_supercombo_karnbirrlv2.pkl` (~06:38 same session family)
contributing disk/CPU load at startup — **hypothesis**, not confirmed; the log doesn't
time-stamp that write against this boot).

## Recommendation

If it recurs: grab `swaglog`/`system logcat` around the bad boot (rlog alone can't see
pandad health — this fork doesn't log pandaState). Waiting ~15 s after ignition before
engaging covers the normal settle window; route 30's failure was beyond that and needed
the reboot the user did.
