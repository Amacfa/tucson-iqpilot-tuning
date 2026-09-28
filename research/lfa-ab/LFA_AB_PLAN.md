# "Check LFA System" — stationary A/B plan (offline package, not installed)

## Why an IQ-side A/B
Alex: the yellow "Check Lane Following Assist (LFA) System" popup does not appear with
the comma unplugged. Raw-CAN analysis (research/lanechange-lfa) showed the popup is the
camera's own 2 s self-warning (LFA 0x12a: LKA_MODE 1→7, FCA_SYSWARN=1, VALUE63=15;
cluster 0x1e0 HDA_InfoPUDis=3), 66 events / 59 segments, at any speed including parked
with the engine on (~2–3 events/min in the driveway), with IQ enabled, disabled or
overridden, MDPS fault bits 0, and no frame-timing gaps. Together: the camera objects to
something IQ sends/relays, not to the steering hardware, and it can be tested parked.

## What the camera sees differently with the comma present
Checked in the panda safety source (`safety/modes/hyundai_canfd.h`, identical recorded vs
current release): 0xea (MDPS) and 0x2af (steering touch) are `check_relay` blocked, so the
camera sees only IQ's relayed copies (Teal's duplicate-feedback fix is present). Relayed
MDPS timing and content were checked in the exports: no gaps, no status-field changes
around events. Remaining IQ-vs-stock differences the camera can observe or react to:

| family | IQ today | stock camera |
|---|---|---|
| LFA 0x12a to the car | built from scratch: LKA_MODE 2, HAS_LANE_SAFETY 0, NEW_SIGNAL_1 0, DampingGain 0 while steering | LKA_MODE 1, HAS_LANE_SAFETY 1, NEW_SIGNAL_1 8, DampingGain 100 |
| MDPS 0xea relayed to camera | LKA_ACTIVE rewritten to follow the camera's STEER_REQ; +220 col-torque "hands-on" spoof 0.4 s every 10 s (also touch 0x2af) | unmodified |
| cluster 0x1e0 to the car | copied from camera, HDA_LFA_SymSta / HDA_CntrlModSta forced 0 unless IQ active | camera's own values |
| SCC/ADRV (IQ long on) | IQ's SCC_CONTROL/ADRV frames replace the camera's | camera's |

## Package
`package/` patches one file (`iqdbc/car/hyundai/hyundaicanfd.py`, release 3736edc) and adds a
bit-mask switch read once per start from `/data/tucson_lfa_ab` (missing = 0 = release
behavior, byte-identical output verified offline):

- bit 1: LFA built from the camera's frame, only LKA_ICON/TORQUE_REQUEST/STEER_REQ/DampingGain overridden
- bit 2: MDPS + touch relayed unmodified (no LKA_ACTIVE rewrite, no hands-on spoof)
- bit 4: cluster frame passed through unless IQ is actively controlling
- bit 8: DampingGain stays 100 while IQ steers (driving-only relevance; also the lane-change lead)

Native torque limits, rate limits and panda safety are untouched; STEER_REQ/TORQUE_REQUEST
semantics are unchanged in every variant (asserted in `validation/test_variants.py`).
Validation: forward/reverse patch round trip, manage.py transaction tests, variant unit
tests with a local packer (CHECKSUM/byte-equivalence to the device packer not verified —
see RESULTS.md).

## Protocol (parked in the driveway, engine on, comma on Wi-Fi, no driving)
Each step: set variant → parked reboot → wait for IQ ready → sit 5 min → export the
segment and count camera LKA_MODE=7 events (`analysis/lfa/warn_context.py`). Expected
baseline ≈ 10–15 events per 5 min; a variant that drops to 0 is a hit, ≤3 is a maybe.

0. Baseline, variant 0 (current install) — confirm the parked rate first.
1. No-code check: IQ longitudinal OFF in the IQ settings (camera SCC/ADRV frames flow
   again) — isolates the SCC/ADRV family without any patch.
2. variant 1 (LFA fields), 3. variant 2 (MDPS relay), 4. variant 4 (cluster),
   5. variant 7 (all three) if none alone is decisive.
6. Only after a stationary hit: one supervised drive on that variant to confirm the popup
   is gone while moving and that steering feel/arming are unchanged.

## Not done / not claimed
Nothing installed. No variant has physical evidence yet. Semantics of LKA_MODE,
HAS_LANE_SAFETY, NEW_SIGNAL_1, DampingGain remain inferred from the stock camera's values.

## Install log
- 2026-09-28 23:26Z: package installed on the comma (parked, IsOffroad=1), variant file absent
  (= variant 0), parked reboot, `--verify-installed` passed. manage.py fix: post-install verify
  skipped the target file in `validation_dependencies` (it previously required the original hash).
