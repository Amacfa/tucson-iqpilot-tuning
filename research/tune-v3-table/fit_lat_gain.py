#!/usr/bin/env python3
"""Fit effective latAccelFactor + friction vs speed from v3b exports.

Model per speed bin: tqo = ala / K_eff + friction_eff * sign(ala)
  -> HuberRegressor on [ala, sign(ala)] gives slope = 1/K_eff, sign-coef = friction_eff.
Also fits the same against yawRate*vEgo as independent lat accel.
Memory: one segment at a time; only filtered float32 arrays are kept.
"""
import gzip, json, os
import numpy as np
from collections import defaultdict
from sklearn.linear_model import HuberRegressor

EXP = os.environ.get('TUCSON_V3B_DIR', '/home/ubuntu/tucson/drives/export-v3b')
SKIP = {'00000029--af0e2ac1ba--9', '00000002--8b575e90f8--1'}
BINS = [(5, 8), (8, 12), (12, 15), (15, 20), (20, 25), (25, 40)]
TABLE_BP = np.array([8.0, 15.0, 25.0])
TABLE_V = np.array([2.95, 3.35, 3.70])
BOOT = 200
rng = np.random.default_rng(7)


def group(commit, seg):
    if seg.startswith('00000024--'):
        return 'v1_route24'
    if commit.startswith('3736edca'):
        return 'v2'
    if commit.startswith('0b8c190c'):
        return '0b8c190c_pre_tune'
    return 'baseline_pre0b8c190c'


def cooldown(prs, bl, n=150):
    """bool array: True while within n frames after any prs/blinker frame."""
    src = np.flatnonzero(prs | bl)
    out = np.zeros(len(prs), bool)
    for i in src:
        out[i:i + n] = True
    return out


def fit(x_lat, tq):
    """Huber fit tq = a*x + b*sign(x); returns K=1/a, fric=b."""
    if len(x_lat) < 100:
        return None
    X = np.stack([x_lat, np.sign(x_lat)], axis=1)
    try:
        m = HuberRegressor(fit_intercept=False, max_iter=200).fit(X, tq)
        a, b = m.coef_
    except Exception:
        A = np.linalg.lstsq(X, tq, rcond=None)
        a, b = A[0]
    if a <= 0:
        return None
    return 1.0 / a, float(b)


def boot_ci(x_lat, tq):
    ks, fs = [], []
    n = len(x_lat)
    if n < 100:
        return None
    for _ in range(BOOT):
        idx = rng.integers(0, n, min(n, 20000))
        r = fit(x_lat[idx], tq[idx])
        if r:
            ks.append(r[0]); fs.append(r[1])
    if len(ks) < 50:
        return None
    return (float(np.percentile(ks, 2.5)), float(np.percentile(ks, 97.5)),
            float(np.percentile(fs, 2.5)), float(np.percentile(fs, 97.5)))


acc = defaultdict(lambda: defaultdict(list))  # acc[g][field] -> list of arrays
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
    if len(rows) < 200:
        continue
    gname = group(meta.get('init', {}).get('gitCommit', '?'), seg)
    v = np.array([r.get('v') or 0 for r in rows], np.float32)
    tq = -np.array([r.get('tqo') if r.get('tqo') is not None else (r.get('tq') or 0) for r in rows], np.float32)
    # EPS torque is opposite sign to latAccel; fit in latAccel sign convention
    ala = np.array([r.get('ala') or 0 for r in rows], np.float32)
    dla = np.array([r.get('dla') or 0 for r in rows], np.float32)
    rate = np.array([r.get('rate') or 0 for r in rows], np.float32)
    yaw = np.array([r.get('yaw') or 0 for r in rows], np.float32)
    prs = np.array([r.get('prs') or 0 for r in rows], np.int8)
    bl = np.array([(r.get('lb') or 0) or (r.get('rb') or 0) for r in rows], np.int8)
    lat = np.array([r.get('lat') or 0 for r in rows], np.int8)
    en = np.array([r.get('en') or 0 for r in rows], np.int8)
    act = np.array([r.get('act') or 0 for r in rows], np.int8)
    cool = cooldown(prs.astype(bool), bl.astype(bool))
    m = ((lat == 1) & (en == 1) & (act == 1) & (prs == 0) & ~cool &
         (np.abs(rate) < 15) & (np.abs(ala) >= 0.15) & (np.abs(ala) <= 2.5) &
         (np.abs(tq) < 0.9) & (v >= 5))
    if m.sum():
        a = acc[gname]
        a['v'].append(v[m]); a['tq'].append(tq[m]); a['ala'].append(ala[m])
        a['dla'].append(dla[m]); a['yawlat'].append((yaw[m] * np.pi / 180.0) * v[m])
    del rows

groups = sorted(acc)
print(f"{'group':22s} {'bin':6s} {'n':>7s} {'K_eff':>6s} {'K_CI':>15s} {'fric':>7s} {'f_CI':>15s} {'table':>5s} {'tbl/K':>6s} {'track':>6s} {'K_yaw':>6s} {'f_yaw':>7s}")
md = []
for gname in groups:
    d = {k: np.concatenate(vv) for k, vv in acc[gname].items()}
    md.append(f'## {gname}\n')
    md.append('| bin | n | K_eff (ala) | 95% CI | friction_eff | 95% CI | table@center | table/K | tracking | K_eff (yaw) | friction (yaw) |')
    md.append('|---|---|---|---|---|---|---|---|---|---|---|')
    for lo, hi in BINS:
        m = (d['v'] >= lo) & (d['v'] < hi)
        n = int(m.sum())
        if n < 100:
            print(f"{gname:22s} {lo}-{hi:<4d} n={n} (skip)")
            continue
        x = d['ala'][m]; t = d['tq'][m]
        r = fit(x, t)
        ci = boot_ci(x, t)
        xy = d['yawlat'][m]
        myaw = np.abs(xy) >= 0.15
        ry = fit(xy[myaw], t[myaw]) if myaw.sum() > 100 else None
        ctr = (lo + hi) / 2
        tbl = float(np.interp(ctr, TABLE_BP, TABLE_V))
        tr = float('nan')
        md2 = (np.abs(d['dla'][m]) > 0.3)
        if md2.sum() > 300:
            tr = float(np.median(d['ala'][m][md2] * np.sign(d['dla'][m][md2])) / np.median(np.abs(d['dla'][m][md2])))
        K = r[0] if r else float('nan'); fr = r[1] if r else float('nan')
        kci = f"{ci[0]:.2f}-{ci[1]:.2f}" if ci else '-'
        fci = f"{ci[2]:.3f}-{ci[3]:.3f}" if ci else '-'
        Ky = f"{ry[0]:.2f}" if ry else '-'; fy = f"{ry[1]:.3f}" if ry else '-'
        print(f"{gname:22s} {lo}-{hi:<4d} {n:7d} {K:6.2f} {kci:>15s} {fr:7.3f} {fci:>15s} {tbl:5.2f} {tbl/K:6.2f} {tr:6.3f} {Ky:>6s} {fy:>7s}")
        md.append(f'| {lo}–{hi} | {n} | {K:.2f} | {kci} | {fr:.3f} | {fci} | {tbl:.2f} | {tbl/K:.2f} | {tr:.3f} | {Ky} | {fy} |')
    md.append('')

open('/home/ubuntu/tucson/analysis/wobble/LAT_GAIN_FIT.md', 'w').write(
    '# latAccelFactor + friction fit vs speed (v3b)\n\n'
    'Model: `tqo = ala / K_eff + friction_eff·sign(ala)` (Huber on [ala, sign(ala)]).\n'
    'Steady-state: lat active & engaged, prs==0, |rate|<15 deg/s, 0.15≤|ala|≤2.5, |tqo|<0.9, '
    'v≥5, 1.5 s cooldown after steerPressed/blinker.\n'
    'Current table: [8,15,25] → [2.95,3.35,3.70]. tracking = median(ala·sign(dla))/median|dla| on |dla|>0.3.\n'
    'K_yaw refits torque vs yawRate·vEgo (independent measure).\n\n'
    + '\n'.join(md))
print('wrote LAT_GAIN_FIT.md')
