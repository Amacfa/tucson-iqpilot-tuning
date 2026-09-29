#!/usr/bin/env python3
"""Friction term + 40 mph jitter analysis (v3b export).

NOTE on fields: torqueState exports p, i, d, f, output — there is NO separate
friction term. pid_log.f is the whole feedforward (future desired lat accel +
latAccelOffset + friction contribution, lat-accel space). So 'f' is the
friction-carrying term; phase stats below are f-vs-p, stated as such.

(1) per 15-20 m/s oscillation episode (closeout detector): dominant freq of -tqo
    (0.5-3 Hz), corr(f,p), corr(f,rate), rms(f)/rms(out).
(2) straight steady stretches (|dla|<0.3, same gating): rms(f) vs rms(-tqo) per group.
(3) sim via sim_v3_table-style driver: handback + curve-exit with v3 table,
    friction in {0.12, 0.09, 0.06}; plus v3 + handback fix (p x0.6 >15 m/s + 0.3 s
    friction-input smoothing) = sim_handback cfg C.
One segment at a time; only per-episode/per-stretch scalars kept."""
import gzip, json, os
import numpy as np
from collections import defaultdict, Counter

EXP = os.environ.get('TUCSON_V3B_DIR', '/home/ubuntu/tucson/drives/export-v3b')
SKIP = {'00000029--af0e2ac1ba--9', '00000002--8b575e90f8--1'}


def group(commit, seg):
    if seg.startswith('00000024--'): return 'v1_route24'
    if commit.startswith('3736edca'): return 'v2'
    if commit.startswith('0b8c190c'): return '0b8c190c_pre_tune'
    return 'baseline_pre0b8c190c'


def band_pow_frac(x, dt, lo=0.5, hi=3.0):
    x = np.asarray(x, float) - np.mean(x)
    n = len(x)
    X = np.fft.rfft(x * np.hanning(n)); fr = np.fft.rfftfreq(n, dt)
    p = np.abs(X) ** 2
    bp = p[(fr >= lo) & (fr <= hi)].sum()
    tot = p[1:].sum()
    dom = float(fr[1:][np.argmax(p[1:])]) if tot > 0 else 0.0
    return (bp / tot if tot > 0 else 0.0), np.sqrt(2 * bp) / n * 2, dom


def corr(a, b):
    a = np.asarray(a, float); b = np.asarray(b, float)
    if a.std() < 1e-9 or b.std() < 1e-9:
        return np.nan
    return float(np.corrcoef(a, b)[0, 1])


episodes = defaultdict(list)   # per group list of dicts
steady = defaultdict(lambda: defaultdict(list))  # g -> 'f'/'tq' -> arrays of rms
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
    if len(rows) < 400:
        continue
    g = group(meta.get('init', {}).get('gitCommit', '?'), seg)
    T = np.array([r['t'] for r in rows]); V = np.array([r.get('v') or 0 for r in rows])
    ALA = np.array([r.get('ala') or 0 for r in rows]); DLA = np.array([r.get('dla') or 0 for r in rows])
    TQ = -np.array([r.get('tqo') if r.get('tqo') is not None else (r.get('tq') or 0) for r in rows])
    F = np.array([r.get('f') or 0 for r in rows]); P = np.array([r.get('p') or 0 for r in rows])
    # f is in lat-accel space; convert to torque units via the release's table so rms ratios are comparable
    laf = np.interp(V, [8.0, 15.0, 25.0], [2.95, 3.35, 3.70]); F_TQ = F / laf; P_TQ = P / laf
    RATE = np.array([r.get('rate') or 0 for r in rows])
    ok = np.array([bool(r.get('lat')) and not r.get('prs') and r.get('act') == 1 for r in rows])
    dt = float(np.median(np.diff(T))) if len(T) > 1 else 0.01
    n = len(rows); step = max(int(3.0 / dt), 10)
    # (1) episodes — same detector as closeout_v3b
    i = 0
    while i + step < n:
        s = slice(i, i + step)
        i += step
        if not (ok[s].all() and V[s].mean() >= 5):
            continue
        err = ALA[s] - DLA[s]
        frac, amp, dom = band_pow_frac(err, dt)
        if not (frac > 0.6 and amp > 0.4):
            continue
        _, _, tqdom = band_pow_frac(TQ[s], dt)
        episodes[g].append(dict(seg=seg, v=round(float(V[s].mean()), 1),
                                amp=round(float(amp), 2), dom_err=round(dom, 2), dom_tq=round(tqdom, 2),
                                corr_fp=round(corr(F_TQ[s], P_TQ[s]), 2),
                                corr_fr=round(corr(F_TQ[s], RATE[s]), 2),
                                f_rms=round(float(np.sqrt(np.mean(F_TQ[s] ** 2))), 3),
                                tq_rms=round(float(np.sqrt(np.mean(TQ[s] ** 2))), 3)))
    # (2) straight steady: |dla|<0.3 windows 3 s
    i = 0
    while i + step < n:
        s = slice(i, i + step)
        i += step
        if ok[s].all() and V[s].mean() >= 5 and np.abs(DLA[s]).max() < 0.3:
            steady[g]['f'].append(float(np.sqrt(np.mean(F_TQ[s] ** 2))))
            steady[g]['tq'].append(float(np.sqrt(np.mean(TQ[s] ** 2))))
            steady[g]['p'].append(float(np.sqrt(np.mean(P_TQ[s] ** 2))))
            steady[g]['v'].append(float(V[s].mean()))

print('== oscillation episodes (3 s windows, frac>0.6 amp>0.4) ==')
for g in sorted(episodes):
    eps = episodes[g]
    print(f'{g}: n={len(eps)}')
    bins = defaultdict(list)
    for e in eps:
        b = '15-20' if 15 <= e['v'] < 20 else ('10-15' if 10 <= e['v'] < 15 else 'other')
        bins[b].append(e)
    for b, es in sorted(bins.items()):
        cfp = np.array([e['corr_fp'] for e in es]); cfr = np.array([e['corr_fr'] for e in es])
        lock = np.mean(cfp < -0.3); same = np.mean(np.abs(cfp) > 0.5)
        rr = np.array([e['f_rms'] / max(e['tq_rms'], 1e-9) for e in es])
        doms = Counter(round(e['dom_tq'], 1) for e in es)
        print(f'  {b}: n={len(es)} corr_fp_med={np.nanmedian(cfp):.2f} corr_fr_med={np.nanmedian(cfr):.2f} '
              f'frac_anti={lock:.2f} frac_|corr|>0.5={same:.2f} f/tq_rms_med={np.median(rr):.2f} dom_freq={dict(sorted(doms.items()))}')
print('== straight steady (|dla|<0.3): rms terms ==')
for g in sorted(steady):
    f = np.array(steady[g]['f']); t = np.array(steady[g]['tq']); p = np.array(steady[g]['p'])
    print(f'{g}: n={len(f)} rms_f={np.median(f):.3f} rms_p={np.median(p):.3f} rms_tq={np.median(t):.3f} f/tq={np.median(f/np.maximum(t,1e-9)):.2f}')

json.dump({'episodes': dict(episodes)},
          open('/home/ubuntu/tucson/analysis/wobble/friction_episodes.json', 'w'), indent=1)
