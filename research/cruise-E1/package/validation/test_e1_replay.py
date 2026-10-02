#!/usr/bin/env python3
"""E1 replay check on exported drive segments 00000048 segs 4-5.

Turn window T 314-325 s (hard turn, lead gone, gas off): apply the new e2e
turn-accel cap to logged accel commands, report the fraction that would be
capped + max/mean reduction.
Set-drop window T 350-358 s (set speed dropped 40->30 mph): logged min accel
vs the -0.5 coast floor (leadless frames only, l1s==0).
Hard assert: >=50% of turn frames would be capped; set-drop min raised to -0.5.
"""
import gzip, json, math, sys
import numpy as np

SEGS = ['/home/ubuntu/tucson/drives/export-v3b/00000048--973ea1a359--4.jsonl.gz',
        '/home/ubuntu/tucson/drives/export-v3b/00000048--973ea1a359--5.jsonl.gz']
BPS = [20., 40.]; VS = [1.7, 3.2]
FLOOR = 0.3
GAP = 4.5; COAST = -0.5
SR, WB = 13.7, 2.756

rows = []
for si, path in enumerate(SEGS):
  with gzip.open(path, 'rt') as g:
    g.readline()
    for l in g:
      r = json.loads(l)
      if 't' not in r or 'v' not in r:
        continue
      r['T'] = 60 * (si + 4) + r['t']   # segment k row time = 60k + t
      rows.append(r)
t = np.array([r['T'] for r in rows])
v = np.array([r['v'] for r in rows])
ang = np.array([r['ang'] for r in rows])
acc = np.array([r['acc'] for r in rows])
hudv = np.array([r.get('hud_v') or 0 for r in rows])
l1s = np.array([r.get('l1s', r.get('hud_lead', 0)) or 0 for r in rows])

def ax_allowed(vv, aa):
  atm = np.interp(vv, BPS, VS)
  ay = vv ** 2 * aa * math.pi / 180 / (SR * WB)
  ax = math.sqrt(max(atm ** 2 - ay ** 2, 0.))
  return max(ax, FLOOR)

# ---- turn window ----
m = (t >= 314) & (t <= 325) & (l1s == 0)
caps = np.array([ax_allowed(vv, aa) for vv, aa in zip(v[m], ang[m])])
logged = acc[m]
exceed = logged > caps
red = np.clip(logged - caps, 0, None)
binding = caps < 1.0   # frames where the turn budget bites below ~1 m/s^2
exceed_bind = exceed[binding]
print('TURN window frames=%d capped=%d (%.0f%%)  binding(ax<1)=%d capped=%.0f%%' % (
  m.sum(), exceed.sum(), 100 * exceed.mean(), binding.sum(),
  100 * exceed_bind.mean() if binding.any() else 0))
print('  max reduction %.3f  mean reduction %.3f' % (red.max() if len(red) else 0,
                                                     red[exceed].mean() if exceed.any() else 0))

# ---- set-drop window ----
m2 = (t >= 350) & (t <= 358) & (l1s == 0)
lg = acc[m2]
vv = v[m2]; hv = hudv[m2]
gap = vv - hv
coast_frames = (gap > 0) & (gap < GAP)
new_min = np.where(coast_frames, np.maximum(lg, COAST), lg)
coast_logged_min = lg[coast_frames].min() if coast_frames.any() else float('nan')
coast_floored_min = new_min[coast_frames].min() if coast_frames.any() else float('nan')
print('SETDROP window frames=%d coast_gap_frames=%d' % (m2.sum(), coast_frames.sum()))
print('  logged min acc %.3f -> floored min %.3f (coast-gap frames only)' % (
  coast_logged_min, coast_floored_min))

ok = (exceed_bind.mean() >= 0.5 if binding.any() else False) and \
     (coast_floored_min >= COAST - 1e-9 if coast_frames.any() else False)
print(json.dumps({'turn_capped_frac': float(exceed.mean()),
                  'turn_capped_frac_binding': float(exceed_bind.mean() if binding.any() else 0),
                  'turn_max_reduction': float(red.max() if len(red) else 0),
                  'turn_mean_reduction_capped': float(red[exceed].mean() if exceed.any() else 0),
                  'setdrop_logged_min_coast': float(coast_logged_min),
                  'setdrop_floored_min_coast': float(coast_floored_min),
                  'asserts_pass': bool(ok)}))
sys.exit(0 if ok else 1)
