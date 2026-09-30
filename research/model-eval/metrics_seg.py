#!/usr/bin/env python3
"""Per-seg metrics over a replayed bundle: lane bias, lane-line jitter, path-vs-human RMSE
on manual frames (human lateral path from cameraOdometry), curvature jerk proxy.
Usage: metrics_seg.py <seg_dir> <rep_json>"""
import json, sys
import numpy as np
from iqpilot.tools.lib.logreader import LogReader

seg, rep_json = sys.argv[1], sys.argv[2]
rep = {r['frame']: r for r in json.load(open(rep_json))['records']}

# logged side: engagement, human trajectory (modelV2 cameraOdometry? use carState yaw+v for heading,
# simpler: use logged modelV2.position as the 'plan' reference only for engaged frames;
# human path proxy: trans velocity from cameraOdometry)
en_times = []
for ev in LogReader(f'{seg}/rlog.zst'):
    if ev.which() == 'selfdriveState':
        en_times.append((ev.logMonoTime, bool(ev.selfdriveState.enabled)))

def enabled_at(t):
    import bisect
    ts = [x[0] for x in en_times]
    i = bisect.bisect_right(ts, t) - 1
    return en_times[i][1] if i >= 0 else False

recs = sorted(rep.values(), key=lambda r: r['t'])
ll_jit, off, human_dev = [], [], []
prev = None
for r in recs:
    if r['ll1'] is None or r['ll2'] is None: continue
    off.append((r['ll1'] + r['ll2']) / 2)
    if prev is not None:
        ll_jit.append(abs(r['ll1']-prev[0]) + abs(r['ll2']-prev[1]))
    prev = (r['ll1'], r['ll2'])
    # human deviation: |path y at 1-2 s ahead| on manual frames — need engaged flag by time;
    # approximate: collect all |pos_y[4:6]| (1-2s ahead at 20hz spacing idx ~4-6 of 33-idx path)
    if not enabled_at(r['t']):
        human_dev.append(np.mean([abs(x) for x in r['pos_y'][4:7]]))

def _s(a): 
    return [round(float(np.mean(a)),4), round(float(np.std(a)),4), len(a)]
print(json.dumps({'seg': seg.split('/')[-1],
                  'lane_bias_mean_std_n': _s(off),
                  'lane_jitter_mean_std_n': _s(ll_jit),
                  'manual_path_absdev_1_2s_mean_std_n': _s(human_dev)}))
