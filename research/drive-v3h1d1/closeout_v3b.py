#!/usr/bin/env python3
"""V3B steering closeout: all metrics, one segment at a time, grouped by release commit."""
import gzip, json, os, math
import numpy as np
from collections import defaultdict, Counter

EXP = os.environ.get('TUCSON_V3B_DIR', '/home/ubuntu/tucson/drives/export-v3b')
SKIP = {'00000029--af0e2ac1ba--9', '00000002--8b575e90f8--1'}

def group(commit, seg):
    if seg.startswith('0000002d--'): return 'v3h1d1'
    if seg.startswith('00000024--'): return 'v1_route24'
    if commit.startswith('3736edca'): return 'v2'
    if commit.startswith('0b8c190c'): return '0b8c190c_pre_tune'
    return 'baseline_pre0b8c190c'

def band_frac(x, dt, lo=0.5, hi=3.0):
    x = np.asarray(x, float)
    if len(x) < 16 or np.all(x == x[0]): return 0.0, 0.0
    x = x - x.mean(); n = len(x)
    X = np.fft.rfft(x * np.hanning(n)); fr = np.fft.rfftfreq(n, dt)
    p = np.abs(X)**2; tot = p[1:].sum()
    if tot <= 0: return 0.0, 0.0
    b = p[(fr >= lo) & (fr <= hi)].sum()
    return b/tot, math.sqrt(2*b)/n

def exits(rows):
    idx=[]; armed=False
    for i,r in enumerate(rows):
        if not r.get('lat'): armed=False; continue
        a=abs(r.get('dla') or 0)
        if a>0.8: armed=True
        elif armed and a<0.3: idx.append(i); armed=False
    return idx

def tq_of(r): return r.get('tqo') or r.get('tq') or 0

exit_rows=defaultdict(list)
osc_hrs=defaultdict(Counter); osc_ep=defaultdict(Counter); osc_worst=defaultdict(list)
hand=defaultdict(list)
track={g:{'a':[],'d':[],'v':[]} for g in ('baseline_pre0b8c190c','0b8c190c_pre_tune','v1_route24','v2','v3h1d1')}
sat=Counter(); actf=Counter()
ovr_frames=Counter(); eng_frames=Counter()
sft=Counter(); sfp=Counter()
skipped=[]

for fn in sorted(os.listdir(EXP)):
    if not fn.endswith('.jsonl.gz'): continue
    seg=fn[:-9]
    if seg in SKIP: skipped.append(seg); continue
    path=f'{EXP}/{fn}'
    try:
        with gzip.open(path,'rt') as g:
            meta=json.loads(g.readline())['meta']
            rows=[]; ev=[]
            for t,svc,body in meta.get('events',[]):
                if svc=='onroadEvents': ev.append((t,set(body)))
            for l in g: rows.append(json.loads(l))
    except Exception as e:
        skipped.append(seg); continue
    g=group(meta.get('init',{}).get('gitCommit','?'),seg)
    t=[r['t'] for r in rows if 'v' in r]
    rows=[r for r in rows if 'v' in r]
    if len(rows)<100: continue

    # --- curve exits (exclude override / lat drop in window, per V2 convention) ---
    for i in exits(rows):
        t0=rows[i]['t']
        w=[r for r in rows if t0<=r['t']<=t0+4.0]
        if len(w)<40: continue
        if any(x.get('prs') for x in w) or any(not x.get('lat') for x in w): continue
        dt=(w[-1]['t']-w[0]['t'])/(len(w)-1)
        tq=[tq_of(x) for x in w]; ala=[x.get('ala') or 0 for x in w]; ang=[x.get('ang') or 0 for x in w]
        f_tq,r_tq=band_frac(tq,dt); f_ala,_=band_frac(ala,dt)
        sgn=[1 if x>0 else -1 for x in tq if abs(x)>0.02]
        exit_rows[g].append(dict(seg=seg,t=round(t0,1),v=w[0].get('v') or 0,f_tq=f_tq,f_ala=f_ala,
            ang_p2p=max(ang)-min(ang),sign_chg=sum(1 for a,b in zip(sgn,sgn[1:]) if a!=b),rms_tq=r_tq*270))

    # --- oscillation episodes (3s windows, err band frac>0.6 amp>0.4) ---
    T=np.array([r['t'] for r in rows]); V=np.array([r.get('v') or 0 for r in rows])
    ALA=np.array([r.get('ala') or 0 for r in rows]); DLA=np.array([r.get('dla') or 0 for r in rows])
    ok=np.array([bool(r.get('lat')) and not r.get('prs') for r in rows])
    W=3.0; i=0; n=len(rows); dt=np.median(np.diff(T)) if len(T)>1 else 0.01
    step=max(int(W/dt),10)
    while i+step<n:
        s=slice(i,i+step)
        if ok[s].all() and V[s].mean()>=5:
            b='5-10' if V[s].mean()<10 else '10-15' if V[s].mean()<15 else '15-20' if V[s].mean()<20 else '20+'
            osc_hrs[g][b]+=W/3600
            err=ALA[s]-DLA[s]; fe,ae=band_frac(err,dt); ae=np.sqrt(2)*np.std(err) if ae==0 else ae*step/2*2/step  # keep osc def: band amplitude ~ sqrt(2*power)/n*2? use original: amp from band
            # match original osc_episodes: amp = sqrt(2*band_power)/n*2
            x=err-err.mean(); nn=len(x); X=np.fft.rfft(x*np.hanning(nn)); fr=np.fft.rfftfreq(nn,dt); p=np.abs(X)**2
            bp=p[(fr>=0.5)&(fr<=3.0)].sum(); amp=np.sqrt(2*bp)/nn*2; frac=bp/p[1:].sum() if p[1:].sum()>0 else 0
            if frac>0.6 and amp>0.4:
                osc_ep[g][b]+=1; osc_worst[g].append((round(amp,2),seg,round(T[i],1),round(V[s].mean(),1)))
        i+=step

    # --- lane-change handback ---
    lcts=sorted(t for t,s in ev if 'laneChange' in s)
    spans=[]
    if lcts:
        s=p=lcts[0]
        for tt in lcts[1:]:
            if tt-p>1.5: spans.append((s,p)); s=tt
            p=tt
        spans.append((s,p))
    for s,e in spans:
        prs_t=[r['t'] for r in rows if s-0.5<=r['t']<=e+0.5 and r.get('prs')]
        t0=(max(prs_t)+0.05) if prs_t else s
        if t0>e+0.5: continue
        w=[r for r in rows if t0<=r['t']<=t0+6.0]
        if len(w)<64: continue
        if any(r.get('prs') for r in w) or not all(r.get('lat') for r in w): continue
        tq=np.array([tq_of(x) for x in w]); ftq,_=band_frac(tq,0.01)
        hand[g].append(dict(seg=seg,v=float(np.mean([x.get('v') or 0 for x in w])),f_tq=ftq))

    # --- tracking ratio (lag 30 frames) ---
    L=30
    idx=np.arange(len(rows)); good=np.array([bool(r.get('lat')) and not r.get('prs') and bool(r.get('act')) for r in rows], dtype=bool)
    idg=idx[good]; idg=idg[idg>=L]
    track[g]['a'].append(ALA[idg]); track[g]['d'].append(DLA[idg-L]); track[g]['v'].append(V[idg])

    # --- saturation, overrides, faults ---
    act=np.array([bool(r.get('lat')) and bool(r.get('act')) for r in rows])
    actf[g]+=int(act.sum())
    sat[g]+=int(sum(1 for r in rows if r.get('sat') and r.get('lat')))
    eng=np.array([bool(r.get('lat')) and bool(r.get('act')) and r.get('v',0)>1 for r in rows])
    eng_frames[g]+=int(eng.sum())
    ovr_frames[g]+=int(sum(1 for r in rows if r.get('prs') and r.get('lat')))
    sft[g]+=sum(1 for r in rows if r.get('sft')); sfp[g]+=sum(1 for r in rows if r.get('sfp'))

groups=['baseline_pre0b8c190c','0b8c190c_pre_tune','v1_route24','v2','v3h1d1']
print('== curve-exit wobble ==')
for g in groups:
    rs=exit_rows[g]
    if not rs: print(g,'n=0'); continue
    print(g,'n=%d f_tq=%.3f f_ala=%.3f ang_p2p=%.1f sign_chg=%.1f band_rms=%.2f'%(
        len(rs),np.mean([r['f_tq'] for r in rs]),np.mean([r['f_ala'] for r in rs]),
        np.mean([r['ang_p2p'] for r in rs]),np.mean([r['sign_chg'] for r in rs]),np.mean([r['rms_tq'] for r in rs])))
print('== oscillation episodes per 10 min (15-20 & 20+) ==')
for g in groups:
    for b in ('10-15','15-20','20+'):
        h=osc_hrs[g][b]; e=osc_ep[g][b]
        if h>0: print(g,b,'hrs=%.3f eps=%d per10min=%.1f'%(h,e,e/h*10 if h else 0))
print('== lane-change handback ==')
for g in groups:
    rs=hand[g]
    if not rs: print(g,'n=0'); continue
    fq=[r['f_tq'] for r in rs]
    print(g,'n=%d median=%.3f mean=%.3f frac>0.5=%.2f'%(len(rs),np.median(fq),np.mean(fq),np.mean([x>0.5 for x in fq])))
print('== tracking ratio (|dla|0.3-0.7, lag 0.3s) ==')
for g in groups:
    a0=np.concatenate(track[g]['a']) if track[g]['a'] else np.array([])
    d0=np.concatenate(track[g]['d']) if track[g]['d'] else np.array([])
    v0=np.concatenate(track[g]['v']) if track[g]['v'] else np.array([])
    for lo,hi,nm in [(5,10,'5-10'),(10,15,'10-15'),(15,20,'15-20'),(20,25,'20-25'),(25,40,'25-40')]:
        m=(v0>=lo)&(v0<hi)&(np.abs(d0)>=0.3)&(np.abs(d0)<0.7)
        if m.sum()>100:
            print(g,nm,'n=%d ratio=%.2f rmse=%.3f'%(m.sum(),np.median(a0[m]*np.sign(d0[m]))/np.median(np.abs(d0[m])),np.sqrt(np.mean((a0[m]-d0[m])**2))))
print('== saturation %% (of active frames) ==')
for g in groups: print(g,'%.4f'%(100*sat[g]/max(actf[g],1)))
print('== steerPressed overrides per 10 min engaged ==')
for g in groups: print(g,'pressed_frac=%.2f%%'%(100*ovr_frames[g]/max(eng_frames[g],1)))
print('== sft/sfp ==')
for g in groups: print(g,sft[g],sfp[g])
print('skipped:',skipped)
