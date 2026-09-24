# FCW notes — the 'fcw' events in the exported dataset

Seven `fcw` onroadEvents across four segments (the earlier long-analysis count):

| segment | t (s) | v (m/s) | actual a | cmd acc | alert |
|---|---|---|---|---|---|
| 00000019--<redacted>--14 | 50.94 | 1.15 | -1.02 | -0.74 | BRAKE! / Risk of Collision (critical) |
| 00000019--<redacted>--3 | 19.87, 20.02, 20.20 | 1.4→1.1 | ≈-1.0 | -0.97→-0.58 | BRAKE! / Risk of Collision (critical) at 19.87 |
| 00000021--<redacted>--1 | 46.07 | 12.05 | -2.93 | -3.5 (floor) | BRAKE! / Risk of Collision (critical) |
| 00000022--<redacted>--6 | 20.96, 21.21 | 2.0→1.5 | ≈-2.07 | -1.26→-0.89 | BRAKE! / Risk of Collision (critical) at 20.96 |

Common shape: system is already decelerating (lon active, controls enabled, `aol=enabled`,
no driver gas/brake) when the `fcw` event + critical "BRAKE! / Risk of Collision"
selfdriveState alert fires. Three of four are low-speed (<2.5 m/s) — close-follow or
stop-approach scenarios; the fourth at 12 m/s coincides with a hard commanded
deceleration (-3.5, the cmd floor).

## What can be determined from the exports

- `fcw` here is the cereal onroadEvents name raised by the IQ/openpilot event stack
  (selfdrived), rendered as the critical BRAKE! alert — it is a *warning* event, not
  proof of AEB intervention. `carControl`/`carOutput` torque and `acc` command are
  negative already before the event, consistent with a planned decel that the FCW
  alert accompanies, not an emergency stop being added.
- Without lead data (v1 exports carry no `radarState`/`modelV2` lead fields) we cannot
  tell whether the trigger was the model's predicted-lead path (modelV2 meta →
  `hardBrakePredicted`-style FCW) or a stock/radar AEB-style lead condition
  (`radarState.leadOne.fcw` exists in the schema but was not captured by the v1
  exporter).

## What cannot be determined without lead data

- Whether the lead was real (vehicle, stationary object) or a false positive.
- Whether the alert timing was early/late relative to an actual threat.
- Whether longitudinal braking authority exceeded the plan at that moment (no
  radarTrackId / lead dRel to correlate).

`export_drive_summary_v2.py` (now the hourly exporter) captures per-frame
`radarState.leadOne` (status/dRel/vRel/vLead/aLeadK/modelProb/fcw),
`modelV2.leadsV3[0]` (prob, x), and `longitudinalPlan` (aTarget/shouldStop/hasLead/
source), so post-457ea8e segments will let us separate model-FCW from radar/lead FCW
and correlate deceleration with a real lead.
