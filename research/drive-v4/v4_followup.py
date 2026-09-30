#!/usr/bin/env python3
# v4 drive follow-ups:
#  (1) sub-threshold wobble hunt: 1.0-3.0 s windows, 1.0-2.5 Hz band, ~0.5x amp
#      threshold, scored jointly on -tqo / ang / ala over route 0000002e.
#  (2) tracking by speed at 1 m/s bins on the undelayed reference, split by
#      |ref| bins, with per-bin mean signed p/i terms; groups v4/v3h1d1/v2.
import os, gzip, json, glob
import numpy as np

EXP = os.environ.get('TUCSON_V3B_DIR', '/home/ubuntu/tucson/drives/export-v3b')
KNOWN_BAD = {'00000029--af0e2ac1ba--9', '00000002--8b575e90f8--1'}
GRP_DELAY = {'v4': 0.15, 'v3h1d1': 0.15, 'v2': 0.30}
BAND = (1.0, 2.5)

def group_of(seg, commit):
    if seg.startswith('0000002e--'): return 'v4'
    if seg.startswith('0000002d--'): return 'v3h1d1'
    if seg.startswith('00000024--'): return None
    if commit.startswith('3736edca'): return 'v2'
    return None

def load(path):
    try:
        with gzip.open(path, 'rt') as g:
            meta = json.loads(g.readline())['meta']
            rows = [r for r in (json.loads(l) for l in g) if 'v' in r]
    except Exception:
        return None, None
    return meta, rows

def band_stats(x, dt, band=BAND):
    x = np.asarray(x, float) - np.mean(x); n = len(x)
    if n < 10: return 0.0, 0.0, 0.0
    X = np.abs(np.fft.rfft(x * np.hanning(n))) ** 2
    fr = np.fft.rfftfreq(n, dt)
    m = (fr >= band[0]) & (fr <= band[1])
    tot = X[fr > 0.05].sum()
    amp = np.sqrt(2 * X[m].sum()) / n * 2
    df = float(fr[m][np.argmax(X[m])]) if m.any() else 0.0
    return (X[m].sum() / tot if tot > 0 else 0.0), amp, df

print('=== PART 1: sub-threshold wobble hunt (route 0000002e) ===')
cands = []
for f_ in sorted(glob.glob(f'{EXP}/0000002e*.jsonl.gz')):
    seg = os.path.basename(f_)[:-9]
    meta, rows = load(f_)
    if not rows: continue
    ev = [(t, set(b)) for t, s, b in meta.get('events', []) if s == 'onroadEvents']
    T = np.array([r['t'] for r in rows]); V = np.array([r.get('v') or 0 for r in rows])
    ALA = np.array([r.get('ala') or 0 for r in rows]); DLA = np.array([r.get('dla') or 0 for r in rows])
    TQ = np.array([-(r.get('tqo') or 0) for r in rows]); P = np.array([r.get('p') or 0 for r in rows])
    F = np.array([r.get('f') or 0 for r in rows]); OUT = np.array([r.get('out') or 0 for r in rows])
    I = np.array([r.get('i') or 0 for r in rows]); ANG = np.array([r.get('ang') or 0 for r in rows])
    PRS = np.array([r.get('prs') or 0 for r in rows])
    ok = np.array([bool(r.get('lat')) and not r.get('prs') for r in rows])
    n = len(rows); dt = np.median(np.diff(T)) if n > 1 else 0.01
    for W in (1.0, 2.0, 3.0):
        st = max(int(W / dt), 10); i = 0
        while i + st < n:
            s = slice(i, i + st)
            if ok[s].all() and V[s].mean() >= 5:
                ft, at, dft = band_stats(TQ[s], dt)
                fa, aa, _ = band_stats(ALA[s], dt)
                fg, ag, _ = band_stats(ANG[s], dt)
                # ~0.5x prior amp threshold (0.4 -> 0.2), band-frac 0.5, joint score
                score = min(ft, 1.0) * at + fa * aa
                if ft > 0.5 and at > 0.2 and aa > 0.15 and ag > 0.8:
                    cands.append((round(score, 3), seg, float(T[i]), float(T[i + st] - T[i]),
                                  float(V[s].mean()), s, dft))
            i += st // 2
# dedupe overlapping candidates (same seg, |t| < 2 s)
cands.sort(key=lambda c: -c[0])
keep = []
for c in cands:
    if not any(c[1] == k[1] and abs(c[2] - k[2]) < 2.0 for k in keep):
        keep.append(c)
for c in keep[:5]:
    score, seg, t0, dur, vm, s, dft = c
    with gzip.open(f'{EXP}/{seg}.jsonl.gz', 'rt') as g:
        g.readline(); rows = [r for r in (json.loads(l) for l in g) if 'v' in r]
    T = np.array([r['t'] for r in rows]); e = slice(np.searchsorted(T, t0), np.searchsorted(T, t0 + dur))
    prs_pre = any(r.get('prs') for r in rows[max(0, e.start - 600):e.start])
    dla_pre = max(abs(r.get('dla') or 0) for r in rows[max(0, e.start - 600):e.start])
    evts = meta_ev = None
    with gzip.open(f'{EXP}/{seg}.jsonl.gz', 'rt') as g:
        meta = json.loads(g.readline())['meta']
    lct = [t for t, s_, b in meta.get('events', []) if s_ == 'onroadEvents' for e2 in b if e2 == 'laneChange']
    lcnear = any(t0 - 8 <= t <= t0 + dur + 2 for t in lct)
    ctx = 'lane-change' if lcnear else ('curve-exit' if dla_pre > 0.8 else ('post-override' if prs_pre else 'straight'))
    rms = lambda k: round(float(np.sqrt(np.mean(np.array([r.get(k) or 0 for r in rows[e]]) ** 2))), 2)
    tqrms = round(float(np.sqrt(np.mean(np.array([-(r.get('tqo') or 0) for r in rows[e]]) ** 2))), 2)
    lead = 'P-led' if rms('p') > rms('f') * 0.6 else 'FF-led'
    print(dict(seg=seg, t=round(t0, 1), dur=round(dur, 1), v=round(vm, 1), freq=round(dft, 2),
               score=score, p=rms('p'), i=rms('i'), f=rms('f'), out=rms('out'), tq=tqrms,
               ctx=ctx, lead=lead, lt13=vm < 13))

print('\n=== PART 2: tracking 1 m/s bins, undelayed ref, unsaturated, unpressed ===')
for grp in ('v4', 'v3h1d1', 'v2'):
    files = {'v4': '0000002e', 'v3h1d1': '0000002d', 'v2': None}[grp]
    acc = {}
    for f_ in sorted(glob.glob(f'{EXP}/*.jsonl.gz')):
        seg = os.path.basename(f_)[:-9]
        if seg in KNOWN_BAD: continue
        meta, rows = load(f_)
        if not rows: continue
        g = group_of(seg, meta.get('init', {}).get('gitCommit', ''))
        if g != grp: continue
        T = np.array([r['t'] for r in rows]); V = np.array([r.get('v') or 0 for r in rows])
        dt = np.median(np.diff(T)) if len(T) > 1 else 0.01
        DLA = np.array([r.get('dla') or 0 for r in rows]); ALA = np.array([r.get('ala') or 0 for r in rows])
        P = np.array([r.get('p') or 0 for r in rows]); I = np.array([r.get('i') or 0 for r in rows])
        SAT = np.array([bool(r.get('sat')) for r in rows])
        okf = np.array([bool(r.get('lat')) and not r.get('prs') for r in rows]) & ~SAT
        sh = int(GRP_DELAY[grp] / dt)
        REF = np.concatenate([DLA[sh:], DLA[-sh:]]) if sh else DLA
        # phase classification from ref crossings
        phase = np.full(len(REF), 'steady', dtype=object)
        cross = np.where((np.abs(REF[1:]) > 0.5) & (np.abs(REF[:-1]) <= 0.5))[0]
        for c in cross: phase[c:c + int(0.6 / dt)] = 'entry'
        drops = np.where((np.abs(REF[1:]) < 0.3) & (np.abs(REF[:-1]) >= 0.3))[0]
        for c in drops: phase[max(0, c - int(0.6 / dt)):c] = 'exit'
        for k in range(len(rows)):
            if not okf[k] or not (5 <= V[k] < 25) or abs(REF[k]) < 0.15: continue
            key = (int(V[k]), 'lt05' if abs(REF[k]) < 0.5 else ('mid' if abs(REF[k]) < 1.5 else 'hi'), phase[k])
            a = acc.setdefault(key, [0, 0.0, 0.0, 0.0, 0.0])
            a[0] += 1; a[1] += ALA[k] * np.sign(REF[k]); a[2] += abs(REF[k]); a[3] += P[k] * np.sign(REF[k]); a[4] += I[k] * np.sign(REF[k])
    print('\n--- %s ---' % grp)
    print('v bin | n | tr | mean_p_signed | mean_i_signed')
    for vb in sorted(set(k[0] for k in acc)):
        for mb in ('lt05', 'mid', 'hi'):
            for ph in ('entry', 'steady', 'exit'):
                a = acc.get((vb, mb, ph))
                if a and a[0] >= 50 and a[2] > 0:
                    print('%d %s %s n=%d tr=%.2f p=%.2f i=%.2f' % (vb, mb, ph, a[0], a[1] / a[2], a[3] / a[0], a[4] / a[0]))
