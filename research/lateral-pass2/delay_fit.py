#!/usr/bin/env python3
"""Steering delay fit: cross-correlate -tqo vs (a) steering rate, (b) d/dt(ala),
on engaged unpressed unsaturated stretches >=8 s, per speed bin per release group.
High-pass = subtract 1 s rolling mean; lags 0..0.8 s at the export rate (~100 Hz).
One segment at a time; only (lag_a, lag_b, v) per stretch is kept."""
import gzip, json, os
import numpy as np
from collections import defaultdict

EXP = os.environ.get('TUCSON_V3B_DIR', '/home/ubuntu/tucson/drives/export-v3b')
SKIP = {'00000029--af0e2ac1ba--9', '00000002--8b575e90f8--1'}
BINS = [(5, 10), (10, 15), (15, 20), (20, 25), (25, 40)]
MAXLAG = 0.8
MIN_S = 8.0


def group(commit, seg):
    if seg.startswith('00000024--'): return 'v1_route24'
    if commit.startswith('3736edca'): return 'v2'
    if commit.startswith('0b8c190c'): return '0b8c190c_pre_tune'
    return 'baseline_pre0b8c190c'


def hp(x, n=100):
    x = np.asarray(x, float)
    if len(x) < n + 4:
        return None
    c = np.convolve(x, np.ones(n) / n, 'same')
    c[:n // 2] = x[:n // 2]; c[-n // 2:] = x[-n // 2:]
    return x - c


def best_lag(x, y, dt):
    """Lag L maximizing corr(x[:-L], y[L:]) — response y delayed behind torque x."""
    ml = int(MAXLAG / dt)
    x = x - x.mean(); y = y - y.mean()
    if x.std() < 1e-6 or y.std() < 1e-6:
        return None, 0.0
    best, bc = None, -2
    for L in range(0, ml + 1):
        a = x[:len(x) - L or None]; b = y[L:]
        if len(a) < 200:
            break
        c = float(np.corrcoef(a, b)[0, 1])
        if c > bc:
            bc, best = c, L
    return best * dt if best is not None else None, bc


res = defaultdict(lambda: defaultdict(list))  # res[g][bin] -> (v, lag_rate, lag_dala, corr_r, corr_d)
for fn in sorted(os.listdir(EXP)):
    if not fn.endswith('.jsonl.gz'):
        continue
    seg = fn[:-9]
    if seg in SKIP:
        continue
    rows = []
    with gzip.open(f'{EXP}/{fn}', 'rt') as g:
        meta = json.loads(g.readline())['meta']
        for l in g:
            r = json.loads(l)
            if 'v' in r:
                rows.append(r)
    if len(rows) < 900:
        continue
    g = group(meta.get('init', {}).get('gitCommit', '?'), seg)
    t = np.array([r['t'] for r in rows]); v = np.array([r.get('v') or 0 for r in rows])
    tq = -np.array([r.get('tqo') if r.get('tqo') is not None else (r.get('tq') or 0) for r in rows])
    ala = np.array([r.get('ala') or 0 for r in rows]); rate = np.array([r.get('rate') or 0 for r in rows])
    ok = np.array([bool(r.get('lat')) and bool(r.get('en')) and r.get('act') == 1
                   and not r.get('prs') and abs(r.get('tqo') or r.get('tq') or 0) < 0.9 and (r.get('v') or 0) >= 5
                   for r in rows])
    dt = float(np.median(np.diff(t)))
    # contiguous ok stretches >= MIN_S
    idx = np.flatnonzero(ok)
    if not len(idx):
        continue
    s0 = idx[0]; prev = idx[0]
    spans = []
    for k in idx[1:]:
        if k != prev + 1 or t[k] - t[prev] > 0.03:
            spans.append((s0, prev)); s0 = k
        prev = k
    spans.append((s0, prev))
    dala = np.gradient(ala, dt)
    for a, b in spans:
        if (b - a + 1) * dt < MIN_S:
            continue
        xh = hp(tq[a:b + 1]); rh = hp(rate[a:b + 1]); dh = hp(dala[a:b + 1])
        if xh is None:
            continue
        lr, cr = best_lag(xh, rh, dt)
        ld, cd = best_lag(xh, dh, dt)
        if lr is None and ld is None:
            continue
        vm = float(v[a:b + 1].mean())
        for lo, hi in BINS:
            if lo <= vm < hi:
                res[g][f'{lo}-{hi}'].append((vm, lr, ld, cr, cd))
                break

for g in sorted(res):
    print(f'== {g} ==')
    for lo, hi in BINS:
        d = res[g].get(f'{lo}-{hi}', [])
        n = len(d)
        if not n:
            continue
        lr = np.array([x[1] for x in d if x[1] is not None]); ld = np.array([x[2] for x in d if x[2] is not None])
        cr = np.array([x[3] for x in d if x[3] is not None]); cd = np.array([x[4] for x in d if x[4] is not None])
        def st(x):
            return f'{np.median(x):.3f} [{np.percentile(x,25):.3f}-{np.percentile(x,75):.3f}]' if len(x) else '-'
        print(f'{lo}-{hi}: n={n} lag_rate={st(lr)}s (corr {np.median(cr):.2f}) lag_dala={st(ld)}s (corr {np.median(cd):.2f})')
