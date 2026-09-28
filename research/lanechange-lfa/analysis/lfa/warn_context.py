"""Context around each camera 'LKA_MODE=7 / FCA_SYSWARN' event: intervals, speed, IQ state, camera vs IQ torque request,
MDPS output torque and driver torque, MDPS LKA_ACTIVE as relayed to the camera (bus 2), and what happened in the 3 s before."""
import glob, os, json
import numpy as np
from decode import EXPORT, decode, load

segs = sorted(os.path.basename(p)[:-9] for p in glob.glob(os.path.join(EXPORT, '*.jsonl.gz')))
rows = []
last_event_abs = None
seg_offsets = {}
for seg in segs:
  route, idx = seg.rsplit('--', 1)
  base = int(idx) * 60.0
  hist = []  # (t, kind, value)
  cam_mode = None; speed = 0.0; sds = {}; iq_tq = None; iq_req = None; cam_tq = None; cam_req = None
  mdps_out = None; drv_tq = None; mdps_act_cam = None; mdps_act_bus0 = None; lka_fault = None
  prs = 0; lat_active = None
  for r in load(seg):
    k = r['k']; t = r['t']
    if k == 'cs':
      speed = r.get('v', speed); prs = r.get('prs', prs); lat_active = r.get('lat', lat_active)
    elif k == 'sds':
      sds = r
    elif k == 'sendcan' and r['a'] == 298:
      d = decode(298, r['d'])
      if d:
        iq_tq = d['TORQUE_REQUEST']; iq_req = d['STEER_REQ']
    elif k == 'can' and r['a'] == 298 and r['b'] == 2:
      d = decode(298, r['d'])
      if not d:
        continue
      cam_tq = d['TORQUE_REQUEST']; cam_req = d['STEER_REQ']
      if cam_mode is not None and d['LKA_MODE'] == 7 and cam_mode != 7:
        rows.append(dict(seg=seg, t=t, abs_t=base + t, v=speed, iq=sds.get('st'), alert=sds.get('alert'), prs=prs, lat=lat_active,
                         iq_tq=iq_tq, iq_req=iq_req, cam_tq=cam_tq, cam_req=cam_req, mdps_out=mdps_out, drv_tq=drv_tq,
                         mdps_act_cam=mdps_act_cam, mdps_act_bus0=mdps_act_bus0, lka_fault=lka_fault,
                         hist=[h for h in hist if t - 3.0 <= h[0] <= t]))
      cam_mode = d['LKA_MODE']
    elif k == 'can' and r['a'] == 234:
      d = decode(234, r['d'])
      if not d:
        continue
      if r['b'] == 0:
        mdps_out = d['STEERING_OUT_TORQUE']; drv_tq = d['STEERING_COL_TORQUE']; mdps_act_bus0 = d['LKA_ACTIVE']; lka_fault = (d['LKA_FAULT'], d['LFA2_FAULT'])
      elif r['b'] == 2:
        if d['LKA_ACTIVE'] != mdps_act_cam:
          hist.append((t, 'mdps_act_cam', d['LKA_ACTIVE']))
        mdps_act_cam = d['LKA_ACTIVE']
    elif k == 'sendcan' and r['a'] == 234:
      pass
    if k == 'sds' and hist and hist[-1][1] == 'iq' and hist[-1][2] == r.get('st'):
      pass
    elif k == 'sds':
      if not hist or hist[-1][1] != 'iq' or hist[-1][2] != r.get('st'):
        hist.append((t, 'iq', r.get('st')))
    if k == 'cs':
      if not hist or hist[-1][1] != 'prs' or hist[-1][2] != prs:
        if hist and hist[-1][1] == 'prs' and hist[-1][2] == prs:
          pass
        else:
          hist.append((t, 'prs', prs))
    hist = [h for h in hist if t - 4 <= h[0]]

print('events:', len(rows))
by_route = {}
for r in rows:
  by_route.setdefault(r['seg'].rsplit('--', 1)[0], []).append(r['abs_t'])
for rt, ts in by_route.items():
  ts = sorted(ts); d = np.diff(ts)
  print(rt, 'n=%d' % len(ts), 'intervals(s):', np.round(d, 1).tolist())
print()
print('speed at event: min %.1f median %.1f max %.1f' % (min(r['v'] for r in rows), np.median([r['v'] for r in rows]), max(r['v'] for r in rows)))
from collections import Counter
print('IQ state at event:', Counter(r['iq'] for r in rows))
print('IQ lat active at event:', Counter(r['lat'] for r in rows))
print('IQ STEER_REQ at event:', Counter(r['iq_req'] for r in rows), ' camera STEER_REQ:', Counter(r['cam_req'] for r in rows))
print('MDPS LKA_ACTIVE seen by camera (bus2) at event:', Counter(r['mdps_act_cam'] for r in rows), ' bus0:', Counter(r['mdps_act_bus0'] for r in rows))
print('MDPS faults at event:', Counter(r['lka_fault'] for r in rows))
print('driver pressed at event:', Counter(r['prs'] for r in rows))
print()
for r in rows:
  print(f"{r['seg']} {r['t']:6.2f} v={r['v']:4.1f} iq={r['iq']:<10} lat={r['lat']} prs={r['prs']} iq_tq={r['iq_tq']} cam_tq={r['cam_tq']} mdps_out={r['mdps_out']} drv={r['drv_tq']} act_cam={r['mdps_act_cam']} hist={[(round(h[0]-r['t'],2),h[1],h[2]) for h in r['hist'] if h[1]!='prs' or True][-6:]}")
json.dump(rows, open('/home/ubuntu/tucson/analysis/lfa/warn_events.json', 'w'), default=str)
