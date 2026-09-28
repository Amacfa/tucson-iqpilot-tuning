#!/usr/bin/env python3
"""Post-curve-exit wobble analysis over exported per-frame jsonl rows.
Curve exit: |desired latAccel| > 0.8 falls below 0.3 while lat-active.
Following 4 s window: 0.5-3 Hz band energy fraction of torque cmd, actual
latAccel, steering angle; p2p steering angle; torque sign changes.
"""
import gzip, json, math, os, sys
import numpy as np

EXP = '/home/ubuntu/tucson/drives/export'
OUT = '/home/ubuntu/tucson/analysis/wobble'
os.makedirs(OUT, exist_ok=True)

def load(seg):
    with gzip.open(f'{EXP}/{seg}.jsonl.gz', 'rt') as g:
        meta = json.loads(g.readline())['meta']
        rows = [json.loads(l) for l in g]
    return meta, rows

def band_energy_frac(x, dt, lo=0.5, hi=3.0):
    x = np.asarray(x, float)
    if len(x) < 16 or np.all(x == x[0]):
        return 0.0, 0.0
    x = x - x.mean()
    n = len(x)
    X = np.fft.rfft(x * np.hanning(n))
    freqs = np.fft.rfftfreq(n, dt)
    p = np.abs(X) ** 2
    tot = p[1:].sum()
    if tot <= 0:
        return 0.0, 0.0
    band = p[(freqs >= lo) & (freqs <= hi)].sum()
    return band / tot, math.sqrt(2 * band) / n  # frac, approx band RMS

def exits(rows):
    """indices where |dla| crosses 0.8->0.3 while lat active."""
    idx = []
    armed_hi = False
    for i, r in enumerate(rows):
        if not r.get('lat'):
            armed_hi = False
            continue
        a = abs(r.get('dla') or 0)
        if a > 0.8:
            armed_hi = True
        elif armed_hi and a < 0.3:
            idx.append(i)
            armed_hi = False
    return idx

def analyze(rows, tag):
    res = []
    for i in exits(rows):
        t0 = rows[i]['t']
        w = [r for r in rows if t0 <= r['t'] <= t0 + 4.0]
        if len(w) < 40:
            continue
        dt = (w[-1]['t'] - w[0]['t']) / (len(w) - 1)
        tq = [r.get('tqo') or r.get('tq') or 0 for r in w]
        ala = [r.get('ala') or 0 for r in w]
        ang = [r.get('ang') or 0 for r in w]
        f_tq, rms_tq = band_energy_frac(tq, dt)
        f_a, rms_a = band_energy_frac(ala, dt)
        f_g, rms_g = band_energy_frac(ang, dt)
        sign = [1 if x > 0 else -1 for x in tq if abs(x) > 0.02]
        schanges = sum(1 for a, b in zip(sign, sign[1:]) if a != b)
        res.append(dict(seg_tag=tag, t=round(t0, 2), v=round(w[0].get('v') or 0, 1),
                        n=len(w), f_tq=round(f_tq, 3), f_ala=round(f_a, 3),
                        f_ang=round(f_g, 3), ang_p2p=round(max(ang) - min(ang), 1),
                        tq_sign_changes=schanges, band_rms_tq=round(rms_tq * 270, 2)))
    return res

# post-install segments
post_segs = [f'00000024--f0646026ab--{i}' for i in range(5)]
# pre-install: all other exported segs
all_segs = sorted(f[:-9] for f in os.listdir(EXP) if f.endswith('.jsonl.gz'))
pre_segs = [s for s in all_segs if not s.startswith('00000024--f0646026ab')]

def speed_bin(v):
    for lo, hi, name in [(5, 10, '5-10'), (10, 15, '10-15'), (15, 20, '15-20'), (20, 25, '20-25'), (25, 45, '25+')]:
        if lo <= v < hi:
            return name
    return None

rows_post, rows_pre = [], []
for s in post_segs:
    m, r = load(s)
    rows_post += analyze(r, s)
for s in pre_segs:
    try:
        m, r = load(s)
    except Exception:
        continue
    rows_pre += analyze(r, s)

from collections import defaultdict
def agg(rows):
    g = defaultdict(list)
    for r in rows:
        b = speed_bin(r['v'])
        if b:
            g[b].append(r)
    out = {}
    for b, rs in sorted(g.items()):
        out[b] = dict(n=len(rs),
                      f_tq=round(np.mean([x['f_tq'] for x in rs]), 3),
                      f_ala=round(np.mean([x['f_ala'] for x in rs]), 3),
                      f_ang=round(np.mean([x['f_ang'] for x in rs]), 3),
                      ang_p2p=round(np.mean([x['ang_p2p'] for x in rs]), 1),
                      tq_sign_changes=round(np.mean([x['tq_sign_changes'] for x in rs]), 1),
                      band_rms_tq_x270=round(np.mean([x['band_rms_tq'] for x in rs]), 2))
    return out

rep = {'post_install': {'exits': len(rows_post), 'by_speed': agg(rows_post)},
       'pre_install': {'exits': len(rows_pre), 'by_speed': agg(rows_pre)}}
json.dump({'post': rows_post, 'pre': rows_pre}, open(f'{OUT}/exits.json', 'w'), indent=1)
print(json.dumps(rep, indent=1))
# worst post exits by band_rms_tq
worst = sorted(rows_post, key=lambda r: -r['band_rms_tq'])[:5]
print('worst post exits:', json.dumps(worst, indent=1))
