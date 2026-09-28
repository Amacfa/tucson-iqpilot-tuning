#!/usr/bin/env python3
"""3-way curve-exit wobble: baseline vs drive1 (v1, 60ms filter) vs v2 drives (routes 25-27)."""
import json, os, sys
import numpy as np
from collections import defaultdict
sys.argv = ['x']
import importlib.util
spec = importlib.util.spec_from_file_location('pw', '/home/ubuntu/tucson/analysis/wobble/postcurve_wobble.py')
# reuse functions without running module body: copy needed defs
src = open('/home/ubuntu/tucson/analysis/wobble/postcurve_wobble.py').read().split('# post-install segments')[0]
exec(src)

def speed_bin(v):
    for lo, hi, name in [(5,10,'5-10'),(10,15,'10-15'),(15,20,'15-20'),(20,25,'20-25'),(25,45,'25+')]:
        if lo <= v < hi: return name
    return None

def analyze2(rows, tag, exclude_override=True):
    out = []
    for r in analyze(rows, tag):
        w = [x for x in rows if r['t'] <= x['t'] <= r['t'] + 4.0]
        r['override'] = any(x.get('prs') for x in w)
        r['lat_dropped'] = any(not x.get('lat') for x in w)
        if exclude_override and (r['override'] or r['lat_dropped']):
            continue
        out.append(r)
    return out

all_segs = sorted(f[:-9] for f in os.listdir(EXP) if f.endswith('.jsonl.gz'))
groups = {
  'baseline': [s for s in all_segs if int(s.split('--')[0],16) < 0x24],
  'drive1_v1_filter': [s for s in all_segs if s.startswith('00000024--')],
  'v2_drives_25_27': [s for s in all_segs if 0x25 <= int(s.split('--')[0],16) <= 0x27],
  'v2_drives_28_2a': [s for s in all_segs if int(s.split('--')[0],16) >= 0x28],
}
res = {}
for g, segs in groups.items():
    rows_all = []
    for s in segs:
        try:
            m, r = load(s)
        except Exception as e:
            continue
        rows_all += analyze2(r, s)
    res[g] = rows_all

def agg(rows):
    by = defaultdict(list)
    for r in rows:
        b = speed_bin(r['v'])
        if b: by[b].append(r)
    out = {}
    for b, rs in sorted(by.items()):
        out[b] = dict(n=len(rs), f_tq=round(np.mean([x['f_tq'] for x in rs]),3),
                      f_ala=round(np.mean([x['f_ala'] for x in rs]),3),
                      ang_p2p=round(np.mean([x['ang_p2p'] for x in rs]),1),
                      sign_chg=round(np.mean([x['tq_sign_changes'] for x in rs]),1),
                      band_rms_tq_x270=round(np.mean([x['band_rms_tq'] for x in rs]),2))
    allr = rows
    out['ALL'] = dict(n=len(allr), f_tq=round(np.mean([x['f_tq'] for x in allr]),3) if allr else None,
                      f_ala=round(np.mean([x['f_ala'] for x in allr]),3) if allr else None,
                      ang_p2p=round(np.mean([x['ang_p2p'] for x in allr]),1) if allr else None,
                      sign_chg=round(np.mean([x['tq_sign_changes'] for x in allr]),1) if allr else None,
                      band_rms_tq_x270=round(np.mean([x['band_rms_tq'] for x in allr]),2) if allr else None)
    return out

rep = {g: agg(r) for g, r in res.items()}
print(json.dumps(rep, indent=1))
# per-route for v2
byroute = defaultdict(list)
for r in res['v2_drives_28_2a']:
    byroute[r['seg_tag'].split('--')[0]].append(r)
print('v2 per route:', json.dumps({k: agg(v)['ALL'] for k, v in byroute.items()}, indent=1))
json.dump(res, open(f'{OUT}/exits_v2.json','w'), indent=1)
print('worst v2 exits:', json.dumps(sorted(res['v2_drives_28_2a'], key=lambda r:-r['band_rms_tq'])[:6], indent=1))
