#!/usr/bin/env python3
# Episode detail + comfort analysis for the first v3+H1+D1 drive.
# Part 1: oscillation episodes on 2d segs using closeout_v3b's exact detector,
#         with per-term breakdown and context.
# Part 2: curve metrics incl. comfort set (torque-rate RMS, lateral-jerk RMS,
#         peak lateral jerk, torque sign reversals) for v3h1d1/v2/baseline plus
#         a human reference (lat-inactive curves; proxy lat accel = v^2*ang/L).
import os, gzip, json, glob
import numpy as np

EXP = os.environ.get('TUCSON_V3B_DIR', '/home/ubuntu/tucson/drives/export-v3b')
KNOWN_BAD = {'00000029--af0e2ac1ba--9', '00000002--8b575e90f8--1'}
L = 2.75  # wheelbase m (Tucson)

def band_frac(x, dt):
    x = np.asarray(x, float); x = x - x.mean(); n = len(x)
    X = np.fft.rfft(x * np.hanning(n)); fr = np.fft.rfftfreq(n, dt); p = np.abs(X) ** 2
    bp = p[(fr >= 0.5) & (fr <= 3.0)].sum()
    return (bp / p[1:].sum() if p[1:].sum() > 0 else 0), np.sqrt(2 * bp) / n * 2

def group_of(seg, commit):
    if seg.startswith('0000002d--'): return 'v3h1d1'
    if seg.startswith('00000024--'): return 'v1_route24'
    if commit.startswith('3736edca'): return 'v2'
    if commit.startswith('0b8c190c'): return '0b8c190c_pre_tune'
    return 'baseline_pre0b8c190c'

print('=== PART 1: v3h1d1 episode detail ===')
for f_ in sorted(glob.glob(f'{EXP}/0000002d*.jsonl.gz')):
    seg = os.path.basename(f_)[:-9]
    with gzip.open(f_, 'rt') as g:
        meta = json.loads(g.readline())['meta']
        ev = [(t, set(b)) for t, s, b in meta.get('events', []) if s == 'onroadEvents']
        rows = [r for r in (json.loads(l) for l in g) if 'v' in r]
    T = np.array([r['t'] for r in rows]); V = np.array([r.get('v') or 0 for r in rows])
    ALA = np.array([r.get('ala') or 0 for r in rows]); DLA = np.array([r.get('dla') or 0 for r in rows])
    TQ = np.array([-(r.get('tqo') or 0) for r in rows]); P = np.array([r.get('p') or 0 for r in rows])
    F = np.array([r.get('f') or 0 for r in rows]); OUT = np.array([r.get('out') or 0 for r in rows])
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
                ctx = 'curve-exit' if (np.max(np.abs(DLA[pre])) > 0.8 and np.max(np.abs(DLA[e])) < 0.5) else \
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
                           out_rms=round(float(np.sqrt(np.mean(OUT[e] ** 2))), 2),
                           corr_fp=round(cfp, 2), dla_max=round(float(np.max(np.abs(DLA[e]))), 2)))
                i = e.stop; continue
        i += step // 2

print('\n=== PART 2: curves (|dla|>0.8 >=2s, lat on, no prs) + human ref (lat off, |v^2*ang/L|>0.8) ===')
CUR = {g: [] for g in ('v3h1d1', 'v2', 'baseline_pre0b8c190c', 'human')}
PH = {g: {} for g in CUR}
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
    ANG = np.array([r.get('ang') or 0 for r in rows])
    HALA = V * V * np.radians(ANG) / L  # human-proxy lat accel

    for grp, mask_sig in ((g, (np.abs(DLA) > 0.8) & LAT & ~PRS),
                          ('human', (np.abs(HALA) > 0.8) & ~LAT)):
        if grp not in CUR: continue
        m = mask_sig; i = 0
        while i < len(m):
            if not m[i]: i += 1; continue
            j = i
            while j < len(m) and m[j]: j += 1
            if (j - i) * dt >= 2.0 and float(np.median(V[i:j])) >= 8:
                s = slice(i, j); nn = int(0.6 / dt)
                if grp == 'human':
                    jerk = np.diff(HALA[s]) / dt
                    rev = int(np.sum(np.diff(np.sign(np.diff(ANG[s]))) != 0))
                    rec = dict(v=float(np.median(V[s])), tr_entry=float('nan'), tr_mid=float('nan'),
                               tr_exit=float('nan'), overshoot=float('nan'), tq_rate=float('nan'),
                               p_rms=float('nan'), jerk_rms=float(np.sqrt(np.mean(jerk ** 2))),
                               jerk_pk=float(np.max(np.abs(jerk))), rev=rev,
                               rate_rms=float(np.sqrt(np.mean((np.diff(ANG[s]) / dt) ** 2))),
                               phase=float('nan'))
                else:
                    tr = lambda ss: (float(np.mean(ALA[ss] * np.sign(DLA[ss]))) / float(np.mean(np.abs(DLA[ss])))
                                     if np.mean(np.abs(DLA[ss])) > 0.3 else float('nan'))
                    mid_ss = slice(i + nn, j - nn)
                    ov = float(np.max(np.abs(ALA[i:i + int(1.5 / dt)])) / np.mean(np.abs(DLA[mid_ss]))) \
                        if mid_ss.stop > mid_ss.start and np.mean(np.abs(DLA[mid_ss])) > 0.3 else float('nan')
                    jerk = np.diff(ALA[s]) / dt
                    rev = int(np.sum(np.diff(np.sign(TQ[s][TQ[s] != 0])) != 0)) if np.any(TQ[s] != 0) else 0
                    dd = DLA[i:i + int(2 / dt)]; aa = ALA[i:i + int(2 / dt)]
                    ph = float('nan')
                    if len(dd) > 10 and np.std(dd - dd.mean()) > 0.05 and np.std(aa) > 0.05:
                        c = np.correlate(aa - aa.mean(), dd - dd.mean(), 'full') / (np.std(dd) * np.std(aa) * len(dd))
                        lg = np.arange(-len(dd) + 1, len(dd)); mm = np.abs(lg) <= int(0.8 / dt)
                        ph = float(lg[mm][np.argmax(c[mm])] * dt)
                    rec = dict(v=float(np.median(V[s])), tr_entry=tr(slice(i, i + nn)),
                               tr_mid=tr(slice(i + (j - i) // 3, j - (j - i) // 3)), tr_exit=tr(slice(j - nn, j)),
                               overshoot=ov, tq_rate=float(np.sqrt(np.mean((np.diff(TQ[s]) / dt) ** 2))),
                               p_rms=float(np.sqrt(np.mean(P[s] ** 2))),
                               jerk_rms=float(np.sqrt(np.mean(jerk ** 2))), jerk_pk=float(np.max(np.abs(jerk))),
                               rev=rev, rate_rms=float(np.sqrt(np.mean((np.diff(ANG[s]) / dt) ** 2))), phase=ph)
                    b = '8-15' if rec['v'] < 15 else '15+'
                    PH[grp].setdefault(b, []).append(ph)
                CUR[grp].append(rec)
            i = j

for g, cs in CUR.items():
    if not cs: print(g, 'none'); continue
    a = lambda k: round(float(np.nanmean([c[k] for c in cs])), 3)
    print(g, 'n=%d' % len(cs), '| tr e/m/x:', a('tr_entry'), a('tr_mid'), a('tr_exit'),
          '| overshoot', a('overshoot'), '| tq_rate', a('tq_rate'), '| p_rms', a('p_rms'),
          '| jerk_rms', a('jerk_rms'), '| jerk_pk', a('jerk_pk'), '| rev/crv', a('rev'),
          '| ang_rate_rms', a('rate_rms'))
print('\n=== phase lag at entry (s, +=actual lags desired) ===')
for g, bins in PH.items():
    for b, vs in sorted(bins.items()):
        vs = [x for x in vs if x == x]
        if vs: print(g, b, 'n=%d' % len(vs), 'med %.3f mean %.3f' % (float(np.median(vs)), float(np.mean(vs))))
print('\n=== comfort ratio v3h1d1 / human ===')
for k in ('jerk_rms', 'jerk_pk', 'rev', 'rate_rms'):
    nh = [c[k] for c in CUR['human']] or [float('nan')]
    nv = [c[k] for c in CUR['v3h1d1']] or [float('nan')]
    if all(x == x for x in nh) and all(x == x for x in nv):
        print(k, round(float(np.mean(nv) / np.mean(nh)), 2))
