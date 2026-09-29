# UPSTREAM_COMPARE — "Check Lane Following Assist (LFA) System" vs upstream openpilot

Sources:
- upstream master: commaai/opendbc @ 84ddee33137e (2026-09-28) cloned to /home/ubuntu/tucson/upstream/opendbc (shallow, depth 50 — old history not present, so `git log -S` covers only recent commits; see "unverifiable").
- IQ fork: /home/ubuntu/tucson/src/.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/{hyundaicanfd.py,carcontroller.py} (release-candidate tree)
- IQ DBC: analysis/tucson-motion-estimator-20260922/.../dbc/generator/hyundai/hyundai_canfd.dbc
- IQ panda safety: analysis/tucson-iq-release-candidate-20260921/.../safety/modes/hyundai_canfd.h
- upstream panda: upstream/opendbc/opendbc/safety/modes/hyundai_canfd.h

Note: IQ's hyundaicanfd.py is a carrot/sunpilot-derived superset (create_steering_messages_camera_scc, angle-control, stopping controller, TCS/button relays) — upstream has none of these functions.

## (a) Exact code differences — camera-SCC steering path

### Upstream master (whole steering path, all CAN-FD cars)
`create_steering_messages(packer, CP, CAN, enabled, lat_active, apply_torque)` builds ONE fixed dict
and sends `LFA` on `CAN.ECAN` for LFA-steering cars (non-LKA-steering), plus LKAS/LKAS_ALT on ACAN
for HDA2. That's all — **upstream sends no MDPS, no STEER_TOUCH_2AF, never reads CS.lfa**.
Upstream LFA dict (non-angle):
```python
values = {
  "LKA_OptUsmSta": 2,                       # = IQ DBC "LKA_MODE" (24|3@1+)
  "LKA_SysIndReq": 2 if enabled else 1,     # = "LKA_ICON" (38|3 vs 38|2 — upstream DBC is 3 bits)
  "StrTqReqVal": apply_torque,              # = "TORQUE_REQUEST" (41|11@1+, -1024 offset)
  "LKA_SysWrn": 0,                          # (60|4) — IQ doesn't set it (defaults 0 in DBC)
  "ActToiSta": 1 if lat_active else 0,      # = "STEER_REQ" (52|1/2)
  "LKA_UsmMod": 0,                          # = "HAS_LANE_SAFETY" region (80|2 upstream / 80|1 IQ)
  "LKA_RcgSta": 0,                          # (27|3) — overlaps IQ's "LKA_ACTIVE" (27|2)
  "Damping_Gain": 100,                      # = "DampingGain" (104|8) — ALWAYS 100
}
```
`create_lfahda_cluster(packer, CAN, enabled)` upstream sends a **fixed 2-field** frame
`{HDA_ICON: 1 if enabled else 0, LFA_ICON: 2 if enabled else 0}` on ECAN at 20 Hz —
it does NOT passthrough the camera's LFAHDA_CLUSTER; upstream DBC for 0x1e0 uses generic
NEW_SIGNAL_*/HDA_ICON/LFA_ICON names and is attributed to ADRV, i.e. upstream assumes the ADAS
ECU (disabled by comma) originates it and just keeps icons alive.

### IQ camera-SCC path (`create_steering_messages_camera_scc`, torque branch = our car)
1. **MDPS relay**: `values = copy.copy(CS.mdps)`, rewrites `LKA_ACTIVE` = 1 iff `CS.lfa["STEER_REQ"]==1`,
   adds `STEERING_COL_TORQUE += 220` for 40 of every 1000 frames (HANDS_ON_SPOOF), sends `MDPS`
   onto `CAN.CAM` (bus 2). Panda safety comment at IQ hyundai_canfd.h:110 says check_relay=false
   so the **stock MDPS keeps being forwarded AND openpilot's copy is additive** → camera can see
   two 0xea streams (unverified whether fwd-hook actually forwards MDPS in camera-SCC config —
   TX list adds 0xea on bus 2 with check_relay=false explicitly to allow it).
2. **STEER_TOUCH_2AF** (0x2af) relay on CAM every 10 frames with `TOUCH_DETECT=3, TOUCH1/2=50`
   spoof + `hyundai_crc8` recomputation — entirely absent upstream.
3. **LFA** built from a fresh 8-field dict (NOT copied from camera): LKA_MODE=2, LKA_ICON,
   TORQUE_REQUEST=apply_steer, STEER_REQ, VALUE64=0, HAS_LANE_SAFETY=0, LKA_ACTIVE=0,
   DampingGain=0-if-active-else-100, sent on `CAN.ECAN`.
   → vs upstream same-slot fields: identical except **DampingGain 0-when-active (upstream 100)**
   and upstream sets LKA_SysWrn/LKA_UsmMod/LKA_RcgSta explicitly (IQ leaves them at whatever the
   DBC default/filler gives = 0 — same value).
   → vs the camera's own live frame (CS.lfa, e.g. NEW_SIGNAL_1=8, HAS_LANE_SAFETY=1, LKA_MODE=1):
   IQ's synthesized frame zeroes NEW_SIGNAL_1 (75|4@0), HAS_LANE_SAFETY, LKA_ACTIVE, and writes
   LKA_MODE=2 where the camera sends 1.
4. **LFAHDA_CLUSTER**: IQ copies camera's frame, forces `HDA_CntrlModSta`/`HDA_LFA_SymSta` to
   2-when-active-else-0. Upstream sends fixed icons only.
5. IQ also adds on the camera-SCC bus: TCS relay (0x35 edits), CRUISE_BUTTONS_ALT / button
   forwarding (LFA_BTN trigger), CAM_0x362/0x2a4 LFA suppression, ADRV_* keep-alive frames gated
   OFF for CAMERA_SCC (upstream sends ADRV_0x160/0x1ea/0x200/0x345/0x1da only when
   `lka_steering`; IQ gates them off specifically for CAMERA_SCC — i.e. upstream's camera-SCC
   cars get no ADRV keep-alives either; not a diff).
6. CanBus: for CAMERA_SCC cars `_a,_e` stay 1,0 (ECAN=bus1, CAM=bus2), same as upstream when
   `lka_steering=False`; IQ adds a `HyundaiCameraSCC` param that can flip them (0 on this car →
   stock mapping; verified param read gate `Params().get_int("HyundaiCameraSCC")==0`).

## (b) Fields/messages IQ sends that upstream does not
- `MDPS` (0xea) relay on CAM bus with rewritten `LKA_ACTIVE` + spoofed `STEERING_COL_TORQUE`.
- `STEER_TOUCH_2AF` (0x2af) with spoofed touch sensors + hand-rolled CRC8.
- `LFAHDA_CLUSTER` passthrough-with-rewrite (upstream writes a fixed icon frame).
- `TCS` relay, cruise-button forwarding, `CAM_0x362`/`CAM_0x2a4` suppression, `ADRV_0x161`
  (`create_lfa_icon_non_camera_scc` — not used on camera-SCC).
- LFA content delta vs upstream: `DampingGain` 0-vs-100 while active; `NEW_SIGNAL_1`,
  `VALUE63/64`, `LKAS_ANGLE_*`, `HAS_LANE_SAFETY` all zeroed where the stock camera emits 8/1/…
  (upstream also emits 0s for those bytes since it builds the dict fresh — **the delta here is
  IQ-vs-camera, not IQ-vs-upstream**).

## (c) Evidence-ranked causes for the dash warning

1. **The camera itself is still running LFA behind the relay and declares a fault when the
   actuator feedback it sees is inconsistent** — supported by IQ's own comment ("camera keeps
   running its own LFA/SCC logic behind the relay and faults unless the actuator feedback it
   sees follows its own request") and by the A/B package design. The camera's LFA frame is
   replaced by IQ's synthesized one (ECAN), so the camera sees its own LFA path producing
   STEER_REQ/torque while MDPS (relayed+rewritten) says something else → "Check LFA" is a
   camera-side fault, matching Hyundai docs (warning originates from LFA malfunction detection).
2. **LFA frame content**: cluster/camera expect stock LFA fields (NEW_SIGNAL_1=8,
   HAS_LANE_SAFETY=1, LKA_MODE=1, nonzero COUNTER semantics from camera). IQ zeroes them.
   Precedent that a comma-sent LFA frame can put the car into a faulted "expects LFA" state:
   commaai/openpilot#29552 (Ioniq EV 2020 "Check LFA system" — sshane: car entered persistent
   LFA-expecting state once we sent the message). Note that issue was a *missing-then-sent* LFA
   on a car that never had LFA; ours is content-mismatch — related mechanism, not identical.
3. **MDPS relay + hands-on spoof**: NHTSA recall RCONL-21V447 explicitly ties "Check Lane
   Following Assist (LFA) system" to R-MDPS *communication fault* detection — injecting a second
   additive MDPS stream with modified LKA_ACTIVE/steering-column-torque is exactly the kind of
   inconsistency that trips comms-fault diagnosis. bit2 tests this.
4. **DampingGain 0-vs-100** (lowest ranked — also present upstream-by-default=0 in some forks;
   still, upstream master sends 100 unconditionally → bit8 test).
5. Hardware/cable cause ruled less likely for us but documented upstream:
   commaai/opendbc#2849 (Ioniq 5 HDA2 — "Check LFA system" appeared together with
   "CAN Bus Disconnected: Likely Faulty Cable"; resolved by device replacement) — our drive-1
   data shows no canError during lat-active segments and no steer faults, so software framing
   fits better.

URLs:
- https://github.com/commaai/openpilot/issues/29552
- https://github.com/commaai/opendbc/issues/2849
- https://github.com/commaai/openpilot/pull/25510 (LFAHDA_CLUSTER/HDA icons CAN-FD; shows which ECUs send what)
- https://github.com/commaai/openpilot/pull/29658 (CAM_0x362/0x2a4 LFA suppression on HDA2)
- https://github.com/sunnypilot/opendbc/commit/6720c230ca6a22d0f458dfcc5db5a2352545f623 (camera-SCC long + panda SCC_CONTROL block)
- https://github.com/sunnypilot/opendbc/commit/fe1690d48d586b051cffdcf4b1d2de5cc12d1569 (HDA2→LKA_STEERING refactor; suppress_lfa)
- https://static.nhtsa.gov/odi/rcl/2021/RCONL-21V447-2664.pdf (warning ↔ MDPS comms fault)
- https://github.com/commaai/openpilot/pull/20916 (historical "Check LFA" fixed during port)

## (d) DBC diffs (upstream generator vs IQ generator)
- Upstream renamed the fields: LKA_OptUsmSta/LKA_SysIndReq/StrTqReqVal/ActToiSta/LKA_SysWrn/
  LKA_UsmMod/LKA_RcgSta/Damping_Gain etc. — same bit positions as IQ's LKA_MODE/LKA_ICON/
  TORQUE_REQUEST/STEER_REQ/…/HAS_LANE_SAFETY/LKA_ACTIVE/DampingGain mostly; exceptions:
  upstream LKA_ICON (SysIndReq) is 38|3 vs IQ 38|2; upstream LKA_RcgSta 27|3 vs IQ LKA_ACTIVE
  27|2 — 1 bit wider upstream.
- IQ DBC declares VALUE231/239/247/255 (bytes beyond the 16-byte frame — dead fields,
  cantools-incompatible); upstream LFA has no tail signals.
- IQ MDPS uses old carrot names (LKA_ACTIVE 48|1@0, LKA_FAULT 54|1@0, STEERING_COL_TORQUE
  80|13@1+ off -4095, LFA2_ACTIVE 145|2); upstream now ships full real names
  (MDPS_LkaToiActvSta 48|2@1+, MDPS_LkaFailSta 54|2@1+, MDPS_StrTqSnsrVal 80|13, …).
  **Bit-level mismatch warning**: IQ decodes MDPS bit 48/54 as 1-bit @0 Motorola; upstream
  decodes 2-bit @1 Intel fields at the same offsets. Our CS.mdps dict copy therefore uses IQ's
  naming; the relayed bytes are whatever was decoded+reencoded (self-consistent with IQ DBC).
- IQ LFAHDA_CLUSTER has real HDA_* field names (HDA_LFA_SymSta 47|2@1+, HDA_CntrlModSta 30|2@1+);
  upstream 0x1e0 has only HDA_ICON 31|1 / LFA_ICON 47|2 / NEW_SIGNALs — upstream layout is a
  subset at the same positions (LFA_ICON == HDA_LFA_SymSta slot).

## (e) Unverifiable / open
- Upstream git history before depth-50 not available locally; `git log -S` hits only cover the
  shallow window (no hits for LKA_MODE/DampingGain/HAS_LANE_SAFETY within it — likely because
  those names are carrot-fork names, upstream never had them).
- Whether the panda fwd-hook in the installed camera-SCC configuration actually forwards stock
  0xea alongside the additive relay (comment implies yes; not traced through the fwd-table code).
- Whether "upstream doesn't produce this warning" is true for camera-SCC Tucsons specifically —
  upstream commaai openpilot does not support CAMERA_SCC on Tucson at all (CAMERA_SCC flag is
  carrot/sunpilot/HKG-specific in this codebase lineage; CANFD_CAMERA_SCC exists upstream for
  longitudinal only). So "most users don't see it" is verified for upstream **supported**
  CAN-FD cars but there is no upstream camera-SCC baseline to compare LFA handling against —
  the whole `create_steering_messages_camera_scc` path is fork-only.
