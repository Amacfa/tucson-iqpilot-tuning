# Ran on-device (same env as lanebias_offset.py): path bias = modelV2.position.y sampled at x~15m and x~25m
# per group; output [n, median, mean] per key.
import json, glob, os
import numpy as np
from iqpilot.tools.lib.logreader import LogReader
GROUPS = {'v4': ['0000002e'], 'v3h1d1': ['0000002d'], 'v2': ['00000025','00000028']}
BASE='/data/media/0/realdata'
out={g:{'off':[],'p15':[],'p25':[]} for g in GROUPS}
for grp,prefs in GROUPS.items():
    for p in prefs:
        for seg in sorted(glob.glob(f'{BASE}/{p}--*--*')):
            r=f'{seg}/rlog.zst'
            if not os.path.exists(r): continue
            try:
                eng=False; lat=False; prs=True; v=0.0
                for ev in LogReader(r):
                    w=ev.which()
                    if w=='carState': v=ev.carState.vEgo; prs=ev.carState.steeringPressed
                    elif w=='selfdriveState': eng=bool(ev.selfdriveState.enabled)
                    elif w=='carControl': lat=bool(ev.carControl.latActive)
                    elif w=='modelV2':
                        if not (eng and lat) or prs or v<5: continue
                        m=ev.modelV2; pr=list(m.laneLineProbs)
                        if pr[1]<0.5 or pr[2]<0.5: continue
                        xs=list(m.position.x); ys=list(m.position.y)
                        if len(xs)<3: continue
                        def yat(xt):
                            i=min(range(len(xs)), key=lambda k: abs(xs[k]-xt))
                            return ys[i] if abs(xs[i]-xt)<4 else float('nan')
                        o=out[grp]
                        o['off'].append((m.laneLines[1].y[0]+m.laneLines[2].y[0])/2)
                        o['p15'].append(yat(15.0)); o['p25'].append(yat(25.0))
            except Exception as e:
                print('ERR',seg,repr(e)[:80])
res={}
for g,o in out.items():
    res[g]={k:[int(np.isfinite(np.array(a)).sum()), round(float(np.nanmedian(a)),3), round(float(np.nanmean(a)),3)] for k,a in o.items()}
print(json.dumps(res,indent=1))
