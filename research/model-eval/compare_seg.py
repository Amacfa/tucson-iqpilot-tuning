#!/usr/bin/env python3
"""Compare replayed modelV2 (rep_*.json) vs logged modelV2 in rlog. On-device."""
import json, sys
import numpy as np
from iqpilot.tools.lib.logreader import LogReader

seg, rep_json = sys.argv[1], sys.argv[2]
rep = json.load(open(rep_json))['records']
# logged modelV2
log = []
for ev in LogReader(f'{seg}/rlog.zst'):
    if ev.which() == 'modelV2':
        v = ev.modelV2
        log.append({'t': ev.logMonoTime, 'frame': v.frameId, 'pos_y': list(v.position.y), 'pos_x': list(v.position.x),
                    'll1': v.laneLines[1].y[0] if len(v.laneLines) > 1 else None,
                    'll2': v.laneLines[2].y[0] if len(v.laneLines) > 2 else None,
                    'probs': list(v.laneLineProbs),
                    'vel_x': list(v.velocity.x)})
n = min(len(log), len(rep))
pairs = [(log[i], rep[i]) for i in range(n)]
errs_pos, errs_ll, errs_v = [], [], []
for L, R in pairs:
    ny = min(len(L['pos_y']), len(R['pos_y']))
    errs_pos.extend(abs(np.array(L['pos_y'][:ny]) - np.array(R['pos_y'][:ny])))
    if L['ll1'] is not None and R['ll1'] is not None:
        errs_ll.append(abs(L['ll1'] - R['ll1']) + abs(L['ll2'] - R['ll2']))
    nv = min(len(L['vel_x']), len(R['vel_x']))
    errs_v.extend(abs(np.array(L['vel_x'][:nv]) - np.array(R['vel_x'][:nv])))
def rmse(a): return round(float(np.sqrt(np.mean(np.square(a)))), 4) if len(a) else None
print(json.dumps({'seg': seg.split('/')[-1], 'n_pairs': n,
                  'path_y_rmse_m': rmse(errs_pos),
                  'lane_y0_abs_err_m': rmse(errs_ll),
                  'vel_rmse_ms': rmse(errs_v)}))
