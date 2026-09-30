# Ran on-device: cd /data/openpilot && PYTHONPATH=.venv/lib/python3.12/site-packages:. .venv/bin/python
# Lane-bias aggregator over rlogs: offset=(laneLines[1].y0+laneLines[2].y0)/2, probs>0.5,
# enabled+latActive+unpressed+v>5. Writes /tmp/lanebias_res.json + /tmp/lanebias_cal.json
import json, glob, os
import numpy as np
from iqpilot.tools.lib.logreader import LogReader

GROUPS = {'v4': ['0000002e'], 'v3h1d1': ['0000002d'], 'v2': ['00000025', '00000028']}
BASE = '/data/media/0/realdata'
out = {g: {'off': [], 'w': [], 'v': [], 'path': []} for g in GROUPS}
cal = {}
for grp, prefs in GROUPS.items():
    for p in prefs:
        for seg in sorted(glob.glob(f'{BASE}/{p}--*--*')):
            r = f'{seg}/rlog.zst'
            if not os.path.exists(r): continue
            try:
                eng = False; lat_on = False; prs = True; v = 0.0
                for ev in LogReader(r):
                    w = ev.which()
                    if w == 'carState':
                        cs = ev.carState; v = cs.vEgo; prs = cs.steeringPressed
                    elif w == 'selfdriveState':
                        eng = bool(ev.selfdriveState.enabled)
                    elif w == 'carControl':
                        lat_on = bool(ev.carControl.latActive)
                    elif w == 'extrinsicsCalibration' and grp not in cal:
                        cal[grp] = ev.extrinsicsCalibration.to_dict()
                    elif w == 'modelV2':
                        if not (eng and lat_on) or prs or v < 5: continue
                        m = ev.modelV2
                        probs = list(m.laneLineProbs)
                        yl, yr = m.laneLines[1], m.laneLines[2]
                        if probs[1] < 0.5 or probs[2] < 0.5 or not len(yl.y) or not len(yr.y): continue
                        path = m.position.y[0] if len(m.position.y) else float('nan')
                        o = out[grp]
                        o['off'].append((yl.y[0] + yr.y[0]) / 2)
                        o['w'].append(yl.y[0] - yr.y[0]); o['v'].append(v); o['path'].append(path)
            except Exception as e:
                print('ERR', seg, repr(e)[:100])

res = {}
for grp, o in out.items():
    off = np.array(o['off']); vv = np.array(o['v']); ww = np.array(o['w']); pp = np.array(o['path'])
    r = {'n': len(off)}
    if len(off):
        r['mean'] = round(float(off.mean()), 3); r['med'] = round(float(np.median(off)), 3)
        r['std'] = round(float(off.std()), 3); r['width_med'] = round(float(np.median(ww)), 2)
        r['path_mean'] = round(float(np.nanmean(pp)), 3); r['path_med'] = round(float(np.nanmedian(pp)), 3)
        for lo, hi in ((5, 10), (10, 15), (15, 20), (20, 30)):
            m = (vv >= lo) & (vv < hi)
            if m.sum() > 100:
                r[f'v{lo}-{hi}'] = [int(m.sum()), round(float(np.median(off[m])), 3), round(float(np.nanmedian(pp[m])), 3)]
        medw = np.median(ww)
        for name, m in (('narrow', ww < medw), ('wide', ww >= medw)):
            if m.sum() > 200:
                r[f'w_{name}'] = [int(m.sum()), round(float(np.median(off[m])), 3)]
    res[grp] = r
open('/tmp/lanebias_res.json','w').write(json.dumps(res, indent=1))
open('/tmp/lanebias_cal.json','w').write(json.dumps(cal, indent=1))
print('done')
