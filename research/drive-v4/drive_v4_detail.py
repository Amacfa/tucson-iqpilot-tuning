#!/usr/bin/env python3
# v4 first-drive analysis (route 0000002e). Same detectors as drive_v3h1d1_detail.py.
# Additions vs the v3h1d1 run: per-curve tracking uses the COMMON undelayed reference
# (dla back-shifted by the controller's lat_delay so all groups compare on the same
# signal — D1 lookahead makes the raw dla timing differ), i_rms per curve, and
# low-speed (<13 m/s) episode tracking for the v4 question.
import os, gzip, json, glob
import numpy as np

EXP = os.environ.get('TUCSON_V3B_DIR', '/home/ubuntu/tucson/drives/export-v3b')
KNOWN_BAD = {'00000029--af0e2ac1ba--9', '00000002--8b575e90f8--1'}
L = 2.75
NEW_PREFIX = os.environ.get('ROUTE_PREFIX', '0000002e')
# lat_delay per group for the undelayed reference: v2 = 0.30 (liveDelay), v3h1d1/v4 = 0.15 (D1 clamp)
GRP_DELAY = {'v4': 0.15, 'v3h1d1': 0.15, 'v2': 0.30, 'baseline_pre0b8c190c': 0.30, '0b8c190c_pre_tune': 0.30}

def band_frac(x, dt):
    x = np.asarray(x, float); x = x - x.mean(); n = len(x)
    X = np.fft.rfft(x * np.hanning(n)); fr = np.fft.rfftfreq(n, dt); p = np.abs(X) ** 2
    bp = p[(fr >= 0.5) & (fr <= 3.0)].sum()
    return (bp / p[1:].sum() if p[1:].sum() > 0 else 0), np.sqrt(2 * bp) / n * 2

def group_of(seg, commit):
    if seg.startswith(NEW_PREFIX + '--'): return 'v4'
    if seg.startswith('0000002d--'): return 'v3h1d1'
    if seg.startswith('00000024--'): return 'v1_route24'
    if commit.startswith('3736edca'): return 'v2'
    if commit.startswith('0b8c190c'): return '0b8c190c_pre_tune'
    return 'baseline_pre0b8c190c'

print('=== PART 1: %s episode detail ===' % NEW_PREFIX)
for f_ in sorted(glob.glob(f'{EXP}/{NEW_PREFIX}*.jsonl.gz')):
    seg = os.path.basename(f_)[:-9]
    with gzip.open(f_, 'rt') as g:
        meta = json.loads(g.readline())['meta']
        ev = [(t, set(b)) for t, s, b in meta.get('events', []) if s == 'onroadEvents']
        rows = [r for r in (json.loads(l) for l in g) if 'v' in r]
    T = np.array([r['t'] for r in rows]); V = np.array([r.get('v') or 0 for r in rows])
    ALA = np.array([r.get('ala') or 0 for r in rows]); DLA = np.array([r.get('dla') or 0 for r in rows])
    TQ = np.array([-(r.get('tqo') or 0) for r in rows]); P = np.array([r.get('p') or 0 for r in rows])
    F = np.array([r.get('f') or 0 for r in rows]); OUT = np.array([r.get('out') or 0 for r in rows])
    I = np.array([r.get('i') or 0 for r in rows])
    PRS = np.array([r.get('prs') or 0 for r in rows])
    ok = np.array([bool(r.get('lat')) and not r.get('prs') for r in rows])
    n = len(rows); dt = np.median(np.diff(T)) if n > 1 else 0.01; step = max(int(3.0 / dt), 10)
    i = 0
    while i + step < n:
        s = slice(i, i + step)
        if ok[s].all() and V[s].mean() >= 5:
            frac, amp = band_frac(ALA[s] - DLA[s], dt)
            if frac > 0.6 and amp > 0.4:
                j = i + step
                while j + step < n:
                    s2 = slice(j, j + step)
                    if not (ok[s2].all() and V[s2].mean() >= 5): break
                    f2, a2 = band_frac(ALA[s2] - DLA[s2], dt)
                    if not (f2 > 0.6 and a2 > 0.4): break
                    j += step // 2
                e = slice(i, min(j, n))
                x = TQ[e] - np.convolve(TQ[e], np.ones(max(int(1 / dt), 2)) / max(int(1 / dt), 2), 'same')
                X = np.abs(np.fft.rfft(x * np.hanning(len(x)))); fr = np.fft.rfftfreq(len(x), dt)
                m = (fr >= 0.5) & (fr <= 3.0); df = float(fr[m][np.argmax(X[m])]) if m.any() else float('nan')
                pre = slice(max(0, e.start - int(6 / dt)), e.start)
                pre_dla = np.max(np.abs(DLA[pre])) if pre.stop > pre.start else 0.0
                ctx = 'curve-exit' if (pre_dla > 0.8 and np.max(np.abs(DLA[e])) < 0.5) else \
                      ('post-override' if np.any(PRS[pre]) else 'straight')
                lct = [t for t, s_ in ev if 'laneChange' in s_]
                if any(T[e][0] - 8 <= t <= T[e][-1] + 2 for t in lct): ctx = 'lane-change'
                sm3 = lambda a: np.convolve(a, np.ones(3) / 3, 'same')
                cfp = float(np.corrcoef(sm3(F[e]), sm3(P[e]))[0, 1]) if np.std(P[e]) > 0 else float('nan')
                print(dict(seg=seg, t=round(float(T[e][0]), 1), v=round(float(V[e].mean()), 1),
                           dur=round(float(T[e][-1] - T[e][0]), 1), ctx=ctx, dfreq=round(df, 2),
                           amp_tq=round(float(np.percentile(np.abs(x), 90)), 2),
                           f_rms=round(float(np.sqrt(np.mean(F[e] ** 2))), 2),
                           p_rms=round(float(np.sqrt(np.mean(P[e] ** 2))), 2),
                           i_rms=round(float(np.sqrt(np.mean(I[e] ** 2))), 2),
                           out_rms=round(float(np.sqrt(np.mean(OUT[e] ** 2))), 2),
                           corr_fp=round(cfp, 2), dla_max=round(float(np.max(np.abs(DLA[e]))), 2),
                           lt13=bool(V[e].mean() < 13)))
                i = e.stop; continue
        i += step // 2

print('\n=== PART 2: curves (undelayed ref) + comfort + human ref ===')
CUR = {g: [] for g in ('v4', 'v3h1d1', 'v2', 'baseline_pre0b8c190c', 'human')}
for f_ in sorted(glob.glob(f'{EXP}/*.jsonl.gz')):
    seg = os.path.basename(f_)[:-9]
    if seg in KNOWN_BAD: continue
    try:
        with gzip.open(f_, 'rt') as g:
            meta = json.loads(g.readline())['meta']
            rows = [r for r in (json.loads(l) for l in g) if 'v' in r]
    except Exception:
        continue
    if len(rows) < 200: continue
    g = group_of(seg, meta.get('init', {}).get('gitCommit', ''))
    T = np.array([r['t'] for r in rows]); V = np.array([r.get('v') or 0 for r in rows])
    dt = np.median(np.diff(T)) if len(T) > 1 else 0.01
    LAT = np.array([bool(r.get('lat')) for r in rows]); PRS = np.array([bool(r.get('prs')) for r in rows])
    DLA = np.array([r.get('dla') or 0 for r in rows]); ALA = np.array([r.get('ala') or 0 for r in rows])
    TQ = np.array([-(r.get('tqo') or 0) for r in rows]); P = np.array([r.get('p') or 0 for r in rows])
    I = np.array([r.get('i') or 0 for r in rows])
    ANG = np.array([r.get('ang') or 0 for r in rows])
    HALA = V * V * np.radians(ANG) / L
    # undelayed reference for lat groups: shift dla back by group delay
    if g in GRP_DELAY:
        sh = int(GRP_DELAY[g] / dt)
        REF = np.concatenate([DLA[sh:], DLA[-sh:]]) if sh > 0 else DLA
    else:
        REF = HALA
    for grp, mask_sig, ref in ((g, (np.abs(REF) > 0.8) & LAT & ~PRS, REF),
                               ('human', (np.abs(HALA) > 0.8) & ~LAT, HALA)):
        if grp not in CUR: continue
        m = mask_sig; i2 = 0
        while i2 < len(m):
            if not m[i2]: i2 += 1; continue
            j = i2
            while j < len(m) and m[j]: j += 1
            if (j - i2) * dt >= 2.0 and float(np.median(V[i2:j])) >= 8:
                s = slice(i2, j); nn = int(0.6 / dt)
                tr = lambda ss: (float(np.mean(ALA[ss] * np.sign(ref[ss]))) / float(np.mean(np.abs(ref[ss])))
                                 if np.mean(np.abs(ref[ss])) > 0.3 else float('nan'))
                if grp == 'human':
                    jerk = np.diff(HALA[s]) / dt
                    rec = dict(v=float(np.median(V[s])), tr_e=float('nan'), tr_m=float('nan'), tr_x=float('nan'),
                               tq_rate=float('nan'), p_rms=float('nan'), i_rms=float('nan'),
                               jerk_rms=float(np.sqrt(np.mean(jerk ** 2))), jerk_pk=float(np.max(np.abs(jerk))),
                               rate_rms=float(np.sqrt(np.mean((np.diff(ANG[s]) / dt) ** 2))))
                else:
                    jerk = np.diff(ALA[s]) / dt
                    nz = TQ[s][TQ[s] != 0]
                    rec = dict(v=float(np.median(V[s])), tr_e=tr(slice(i2, i2 + nn)),
                               tr_m=tr(slice(i2 + (j - i2) // 3, j - (j - i2) // 3)), tr_x=tr(slice(j - nn, j)),
                               tq_rate=float(np.sqrt(np.mean((np.diff(TQ[s]) / dt) ** 2))),
                               p_rms=float(np.sqrt(np.mean(P[s] ** 2))), i_rms=float(np.sqrt(np.mean(I[s] ** 2))),
                               jerk_rms=float(np.sqrt(np.mean(jerk ** 2))), jerk_pk=float(np.max(np.abs(jerk))),
                               rev=int(np.sum(np.diff(np.sign(nz)) != 0)) if len(nz) else 0,
                               rate_rms=float(np.sqrt(np.mean((np.diff(ANG[s]) / dt) ** 2))))
                CUR[grp].append(rec)
            i2 = j

for g, cs in CUR.items():
    if not cs: print(g, 'none'); continue
    a = lambda k: round(float(np.nanmean([c[k] for c in cs])), 3)
    print(g, 'n=%d' % len(cs), '| tr e/m/x(undelayed):', a('tr_e'), a('tr_m'), a('tr_x'),
          '| tq_rate', a('tq_rate'), '| p_rms', a('p_rms'), '| i_rms', a('i_rms'),
          '| jerk_rms', a('jerk_rms'), '| jerk_pk', a('jerk_pk'), '| rate_rms', a('rate_rms'))
    if g == 'v4': print('  v4 per-curve (v,tr_x):', [(round(c['v'], 1), round(c['tr_x'], 2)) for c in cs])
    if g == 'v2': print('  v2 per-curve (v,tr_x):', [(round(c['v'], 1), round(c['tr_x'], 2)) for c in cs][:20])
