#!/usr/bin/env python3
# Detailed analysis of the first v3+H1+D1 drive (route 0000002d--7116f1d7a1).
# - all-speed oscillation episode scan with per-term breakdown + context classification
# - curve-segment metrics (tracking entry/mid/exit, entry overshoot, torque-rate RMS,
#   P-term RMS) for v3h1d1 vs v2 vs baseline
# - desired->actual lat accel phase lead/lag at curve entry per speed bin
# - faults / alerts / lateralDelay status summary
# Memory: one segment at a time.
import os, gzip, json, glob, math
import numpy as np

EXP = os.environ.get('TUCSON_V3B_DIR', '/home/ubuntu/tucson/drives/export-v3b')
KNOWN_BAD = {'00000029--af0e2ac1ba--9', '00000002--8b575e90f8--1'}

def grp(seg):
    if seg.startswith('0000002d--'): return 'v3h1d1'
    if seg.startswith('00000024--'): return 'v1_route24'
    return None

def frames(seg):
    try:
        with gzip.open(f'{EXP}/{seg}.jsonl.gz', 'rt') as g:
            meta = json.loads(g.readline())['meta']
            lat = [r for r in (json.loads(l) for l in g) if r.get('lat') == 1 and 'ala' in r]
    except Exception:
        return None, None
    return meta, lat

# ---- oscillation detector (same as closeout): 3s windows, err-band frac>0.6, amp>0.4 ----
def episodes(lat, seg, t0):
    ep = []
    t = np.array([r['t'] for r in lat]); v = np.array([r['v'] for r in lat])
    tq = np.array([-r['tqo'] for r in lat]); err = np.array([r.get('err', 0.0) for r in lat])
    dla = np.array([r.get('dla', 0.0) for r in lat]); prs = np.array([r.get('prs', 0) for r in lat])
    p = np.array([r.get('p', 0.0) for r in lat]); f = np.array([r.get('f', 0.0) for r in lat])
    out = np.array([r.get('out', 0.0) for r in lat]); lc = np.array([r.get('lcst', 0) for r in lat])
    dt = np.median(np.diff(t)) if len(t) > 3 else 0.05
    win = int(3.0 / dt)
    i = 0
    while i + win < len(t):
        w = slice(i, i + win)
        hp = tq[w] - np.convolve(tq[w], np.ones(int(1 / dt)) / int(1 / dt), 'same')
        amp = np.percentile(np.abs(hp), 90)
        band = np.mean(np.abs(err[w]) > 0.15) if False else np.mean(np.abs(hp) > 0.15)
        if band > 0.6 and amp > 0.4:
            # extent: merge consecutive passing windows
            j = i + win
            while j + win < len(t):
                hp2 = tq[j:j + win] - np.convolve(tq[j:j + win], np.ones(int(1 / dt)) / int(1 / dt), 'same')
                if not (np.mean(np.abs(hp2) > 0.15) > 0.6 and np.percentile(np.abs(hp2), 90) > 0.4):
                    break
                j += win // 2
            e = slice(i, min(j, len(t)))
            dur = t[e][-1] - t[e][0]
            # dominant freq of high-passed tq in 0.5-3 Hz
            x = tq[e] - np.convolve(tq[e], np.ones(min(int(1 / dt), len(tq[e]))) / min(int(1 / dt), len(tq[e])), 'same')
            X = np.abs(np.fft.rfft(x * np.hanning(len(x))))
            fr = np.fft.rfftfreq(len(x), dt)
            m = (fr >= 0.5) & (fr <= 3.0)
            df = float(fr[m][np.argmax(X[m])]) if m.any() else float('nan')
            # context
            pre = slice(max(0, e.start - int(6 / dt)), e.start)
            curve_exit = np.max(np.abs(dla[pre])) > 0.8 and np.max(np.abs(dla[e])) < 0.5 if pre.stop > pre.start else False
            lane_chg = np.any(lc[pre] != 0) or np.any(lc[e] != 0)
            post_prs = np.any(prs[pre] != 0)
            ctx = 'curve-exit' if curve_exit else ('lane-change' if lane_chg else ('post-override' if post_prs else 'straight'))
            # per-term breakdown (f,p in lat-accel units -> *2.96 approx? keep raw rms + corr)
            fr_rms = float(np.sqrt(np.mean(f[e] ** 2))); p_rms = float(np.sqrt(np.mean(p[e] ** 2)))
            out_rms = float(np.sqrt(np.mean(out[e] ** 2)))
            corr_fp = float(np.corrcoef(np.convolve(f[e], np.ones(3) / 3, 'same'),
                                        np.convolve(p[e], np.ones(3) / 3, 'same'))[0, 1]) if np.std(p[e]) > 0 else float('nan')
            ep.append(dict(seg=seg, t=round(float(t[e][0] + t0), 1), v=round(float(np.median(v[e])), 1),
                           dur=round(dur, 1), ctx=ctx, dfreq=round(df, 2), amp=round(float(amp), 2),
                           f_rms=round(fr_rms, 2), p_rms=round(p_rms, 2), out_rms=round(out_rms, 2),
                           corr_fp=round(corr_fp, 2), dla=round(float(np.max(np.abs(dla[e]))), 2)))
            i = e.stop
        else:
            i += win // 2
    return ep

# ---- curve segments: |dla|>0.8 for >=2s ----
def curves(lat):
    res = []
    t = np.array([r['t'] for r in lat]); v = np.array([r['v'] for r in lat])
    dla = np.array([r.get('dla', 0.0) for r in lat]); ala = np.array([r['ala'] for r in lat])
    tq = np.array([-r['tqo'] for r in lat]); p = np.array([r.get('p', 0.0) for r in lat])
    prs = np.array([r.get('prs', 0) for r in lat]); lat_en = np.array([r.get('en', 0) for r in lat])
    dt = np.median(np.diff(t)) if len(t) > 3 else 0.05
    m = (np.abs(dla) > 0.8) & (prs == 0) & (lat_en == 1)
    i = 0
    while i < len(m):
        if not m[i]: i += 1; continue
        j = i
        while j < len(m) and m[j]: j += 1
        if (j - i) * dt >= 2.0:
            n = int(0.6 / dt)
            ent, mid, ext = slice(i, i + n), slice(i + (j - i) // 3, j - (j - i) // 3), slice(j - n, j)
            tr = lambda s: (float(np.mean(ala[s] * np.sign(dla[s]))) / float(np.mean(np.abs(dla[s])))
                            if np.mean(np.abs(dla[s])) > 0.3 else float('nan'))
            ss = slice(i + n, j - n)
            overshoot = float(np.max(np.abs(ala[i:i + int(1.5 / dt)])) / np.mean(np.abs(dla[ss]))) if ss.stop > ss.start and np.mean(np.abs(dla[ss])) > 0.3 else float('nan')
            tqr = np.diff(tq[i:j]) / dt
            res.append(dict(v=float(np.median(v[i:j])), dur=round((j - i) * dt, 1),
                            tr_entry=round(tr(ent), 2), tr_mid=round(tr(mid), 2), tr_exit=round(tr(ext), 2),
                            overshoot=round(overshoot, 2), tq_rate_rms=round(float(np.sqrt(np.mean(tqr ** 2))), 2),
                            p_rms=round(float(np.sqrt(np.mean(p[i:j] ** 2))), 2),
                            dla=round(float(np.mean(np.abs(dla[i:j]))), 2),
                            # phase lead: xcorr dla->ala on first 2 s, lags +-0.8s
                            phase=phase_lag(dla[i:i + int(2 / dt)], ala[i:i + int(2 / dt)], dt)))
        i = j
    return res

def phase_lag(d, a, dt):
    # xcorr actual vs desired; positive lag => actual LAGS desired
    n = int(0.8 / dt)
    dd = d - d.mean(); aa = a - a.mean()
    if np.std(dd) < 0.05 or np.std(aa) < 0.05: return float('nan')
    c = np.correlate(aa, dd, 'full') / (np.std(dd) * np.std(aa) * len(dd))
    lags = np.arange(-len(dd) + 1, len(dd))
    m = (lags >= -n) & (lags <= n)
    return round(float(lags[m][np.argmax(c[m])] * dt), 3)

GROUPS = {'v3h1d1': lambda s: s.startswith('0000002d--'),
          'v2': lambda s, c=None: None}

def group_of(seg, commit):
    if seg.startswith('0000002d--'): return 'v3h1d1'
    if seg.startswith('00000024--'): return 'v1_route24'
    if commit.startswith('3736edca'): return 'v2'
    if commit.startswith('0b8c190c'): return '0b8c190c_pre_tune'
    return 'baseline_pre0b8c190c'

NEW_EPS, CURVES = [], {g: [] for g in ('v3h1d1', 'v2', 'baseline_pre0b8c190c')}
PHASE = {g: {} for g in ('v3h1d1', 'v2', 'baseline_pre0b8c190c')}
SAT = {g: [0, 0] for g in ('v3h1d1', 'v2')}
PRS = {g: [0, 0] for g in ('v3h1d1', 'v2')}
ALERTS = []
files = sorted(glob.glob(f'{EXP}/*.jsonl.gz'))
for f_ in files:
    seg = os.path.basename(f_)[:-9]
    if seg in KNOWN_BAD: continue
    meta, lat = frames(seg)
    if not lat: continue
    g = group_of(seg, meta.get('init', {}).get('gitCommit', ''))
    if g == 'v3h1d1':
        NEW_EPS += episodes(lat, seg, 0.0)
        ALERTS += [(seg, a) for a in (meta.get('alerts') or [])]
    if g in CURVES:
        cs = curves(lat)
        CURVES[g] += cs
        for c in cs:
            b = '10-15' if c['v'] < 15 else ('15-20' if c['v'] < 20 else '20+')
            PHASE[g].setdefault(b, []).append(c['phase'])
    if g in SAT:
        for r in lat:
            SAT[g][1] += 1
            if r.get('sat'): SAT[g][0] += 1
            PRS[g][1] += 1 if r.get('en') else 0
            if r.get('prs'): PRS[g][0] += 1

print('=== v3h1d1 episodes ===')
for e in NEW_EPS: print(e)
print('\n=== curves ===')
for g, cs in CURVES.items():
    if not cs: print(g, 'none'); continue
    agg = lambda k: round(float(np.nanmean([c[k] for c in cs])), 3)
    print(g, 'n=%d' % len(cs), 'tr_entry', agg('tr_entry'), 'tr_mid', agg('tr_mid'), 'tr_exit', agg('tr_exit'),
          'overshoot', agg('overshoot'), 'tq_rate', agg('tq_rate_rms'), 'p_rms', agg('p_rms'))
print('\n=== phase lag at curve entry (s, +=actual lags) ===')
for g, bins in PHASE.items():
    for b, vs in sorted(bins.items()):
        vs = [x for x in vs if x == x]
        if vs: print(g, b, 'n=%d' % len(vs), 'med %.3f' % float(np.median(vs)), 'mean %.3f' % float(np.mean(vs)))
print('\n=== saturation / steerPressed ===')
for g in SAT: print(g, 'sat%% %.4f' % (100 * SAT[g][0] / max(SAT[g][1], 1)),
                  'pressed%% %.2f' % (100 * PRS[g][0] / max(PRS[g][1], 1)))
print('\n=== alerts ===')
print(ALERTS[:20] if ALERTS else 'none')
