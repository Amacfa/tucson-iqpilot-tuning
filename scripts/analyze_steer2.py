import numpy as np, json
A = np.load('/home/ubuntu/tucson/drives/all_frames.npy'); C = json.load(open('/home/ubuntu/tucson/drives/all_frames_cols.json'))
ix = {c: i for i, c in enumerate(C)}
def col(n): return A[:, ix[n]]
rid, seg, t = col('rid'), col('seg'), col('t')
v, ala, dla, tq, tqo, p, i_, f, err, act, prs, rate, ang, sat, lat = [col(n) for n in 'v ala dla tq tqo p i f err act prs rate ang sat lat'.split()]
good = (act == 1) & (prs == 0) & (lat == 1)
print('active no-press frames', good.sum())

# ---- 1. speed-dependent plant gain: steady-state (|d tq| small over 0.5s, |rate| small) ----
tq_s = np.convolve(tqo, np.ones(50) / 50, 'same')
dtq = np.abs(tqo - tq_s)
ss = good & (dtq < 0.01) & (np.abs(rate) < 3) & (np.abs(tqo) > 0.05) & (np.abs(tqo) < 0.6)
print('\n== steady-state plant gain (lat accel / torque fraction) by speed')
for lo, hi in [(5, 8), (8, 12), (12, 16), (16, 20), (20, 25), (25, 40)]:
    m = ss & (v >= lo) & (v < hi)
    if m.sum() < 500: continue
    x, y = tqo[m], ala[m]
    # robust fit through origin using medians of ratio in |tq|>0.12 region, and OLS with offset
    r = (y / x)[np.abs(x) > 0.12]
    sl, ic = np.polyfit(x, y, 1)
    # secant model with dead band: fit y = k*(x - db*sign(x)) for |x|>db
    best = None
    for db in np.arange(0, 0.16, 0.01):
        mm = np.abs(x) > db + 0.02
        xx = (np.abs(x[mm]) - db) * np.sign(x[mm]); k = (xx * y[mm]).sum() / (xx * xx).sum(); res = np.mean((y[mm] - k * xx) ** 2)
        if best is None or res < best[2]: best = (db, k, res)
    print('  v %2d-%2d: n=%6d OLS slope %.2f int %+.3f | median ratio(|tq|>.12) %.2f | deadband fit db=%.2f k=%.2f' % (lo, hi, m.sum(), sl, ic, np.median(r), best[0], best[1]))

# ---- 2. lag desired->actual lat accel by speed (cross-corr in 20s windows) ----
print('\n== desired->actual lat-accel lag by speed (20s active windows, corr>0.8)')
res = []
n = len(A); w = 2000
for s in range(0, n - w, w // 2):
    if good[s:s + w].mean() < 0.95 or rid[s] != rid[s + w - 1]: continue
    x = dla[s:s + w] - dla[s:s + w].mean(); y = ala[s:s + w] - ala[s:s + w].mean()
    if x.std() < 0.15: continue
    best = None
    for L in range(0, 100, 2):
        c = np.corrcoef(x[:w - L], y[L:])[0, 1]
        if best is None or c > best[1]: best = (L, c)
    if best[1] > 0.8: res.append((v[s:s + w].mean(), best[0] / 100, best[1], y.std() / x.std()))
R = np.array(res)
for lo, hi in [(5, 10), (10, 15), (15, 20), (20, 25), (25, 40)]:
    m = (R[:, 0] >= lo) & (R[:, 0] < hi)
    if m.sum(): print('  v %2d-%2d: n=%3d lag median %.2fs (p25 %.2f p75 %.2f)  amplitude ratio actual/desired median %.2f' % (lo, hi, m.sum(), np.median(R[m, 1]), *np.percentile(R[m, 1], [25, 75]), np.median(R[m, 3])))

# ---- 3. tracking error by speed and |desired| (with lag-compensated desired 0.3s) ----
print('\n== tracking: actual vs desired(t-0.3s) by speed / |desired| bin')
L = 30
idx = np.flatnonzero(good); idx = idx[idx >= L]; idx = idx[rid[idx] == rid[idx - L]]
d0 = dla[idx - L]; a0 = ala[idx]; v0 = v[idx]
for lo, hi in [(5, 10), (10, 15), (15, 20), (20, 25), (25, 40)]:
    row = []
    for dlo, dhi in [(0.05, 0.3), (0.3, 0.7), (0.7, 1.2), (1.2, 2.0), (2.0, 4)]:
        m = (v0 >= lo) & (v0 < hi) & (np.abs(d0) >= dlo) & (np.abs(d0) < dhi)
        if m.sum() > 300:
            ratio = np.median(a0[m] * np.sign(d0[m])) / np.median(np.abs(d0[m]))
            row.append('|d| %.1f-%.1f: n=%5d ratio %.2f rmse %.3f' % (dlo, dhi, m.sum(), ratio, np.sqrt(np.mean((a0[m] - d0[m]) ** 2))))
    if row: print('  v %2d-%2d:\n     ' % (lo, hi) + '\n     '.join(row))

# ---- 4. dither: quantization analysis ----
print('\n== measurement quantization')
da = np.diff(ang)[good[1:] & good[:-1]]
u = np.unique(np.round(np.abs(da[da != 0]), 3))
print('  smallest nonzero steering-angle step: %.3f deg; step counts (first 5): %s' % (u[0], {float(k): int((np.round(np.abs(da), 3) == k).sum()) for k in u[:5]}))
# ala jump distribution per frame when angle steps by one LSB, by speed
dala = np.diff(ala); m1 = good[1:] & good[:-1] & (np.round(np.abs(da), 3) == u[0]) if False else None
for lo, hi in [(10, 15), (15, 20), (20, 25), (25, 40)]:
    mm = good[1:] & good[:-1] & (v[1:] >= lo) & (v[1:] < hi) & (np.diff(ang) != 0)
    mz = good[1:] & good[:-1] & (v[1:] >= lo) & (v[1:] < hi) & (np.diff(ang) == 0)
    dp = np.diff(p)
    print('  v %2d-%2d: frames with angle step %.0f%%; median |d actualLatAccel| on step %.4f vs no-step %.4f; median |dP| on step %.4f vs %.4f; |d tq|*270 step %.2f vs %.2f' % (
        lo, hi, 100 * mm.sum() / max(1, mm.sum() + mz.sum()), np.median(np.abs(dala[mm])), np.median(np.abs(dala[mz])), np.median(np.abs(dp[mm])), np.median(np.abs(dp[mz])),
        270 * np.median(np.abs(np.diff(tq)[mm])), 270 * np.median(np.abs(np.diff(tq)[mz]))))

# ---- 5. P vs FF sign and I contribution by speed ----
print('\n== controller term stats (active, |desired|>0.3)')
for lo, hi in [(5, 10), (10, 15), (15, 20), (20, 25), (25, 40)]:
    m = good & (v >= lo) & (v < hi) & (np.abs(dla) > 0.3)
    if m.sum() < 500: continue
    s = np.sign(dla[m])
    print('  v %2d-%2d: n=%6d  mean P*sign(des) %+.3f  mean I*sign(des) %+.3f  mean F*sign(des) %+.3f  |P|/|F| %.2f  frac P opposing FF %.2f' % (
        lo, hi, m.sum(), (p[m] * s).mean(), (i_[m] * s).mean(), (f[m] * s).mean(), np.abs(p[m]).mean() / max(np.abs(f[m]).mean(), 1e-6), (np.sign(p[m]) != np.sign(f[m])).mean()))

# ---- 6. driver overrides while active: context ----
print('\n== steering override episodes (pressed >0.3s while lat active)')
pr = (prs == 1) & (lat == 1)
idx = np.flatnonzero(pr); eps = []
if len(idx):
    s0 = pidx = idx[0]
    for k in idx[1:]:
        if k != pidx + 1:
            if pidx - s0 >= 30: eps.append((s0, pidx + 1))
            s0 = k
        pidx = k
E = np.array([[v[s], np.abs(dla[max(0, s - 100):s]).max(), np.abs(err[max(0, s - 100):s]).max(), (e - s) / 100, np.abs(ang[s]), (np.abs(dla[s:e] - ala[s:e])).mean()] for s, e in eps])
print('  n=%d (%.1f/active-hour) v median %.1f; max|desired| in 1s before median %.2f; max|err| before %.2f; dur median %.1fs; frac at |angle|>60deg %.2f; frac at v<8 %.2f' % (
    len(E), len(E) / (good.sum() / 360000), np.median(E[:, 0]), np.median(E[:, 1]), np.median(E[:, 2]), np.median(E[:, 3]), (E[:, 4] > 60).mean(), (E[:, 0] < 8).mean()))
# saturation
print('\n== saturation: frames |tqo|>0.95 while active: %d (%.3f%%), sat flag frames %d' % ((good & (np.abs(tqo) > 0.95)).sum(), 100 * (good & (np.abs(tqo) > 0.95)).mean() / max(good.mean(), 1e-9), (good & (sat == 1)).sum()))
for lo, hi in [(0, 8), (8, 15), (15, 40)]:
    m = good & (v >= lo) & (v < hi)
    print('  v %2d-%2d: p99 |tq| %.2f, frac>0.8 %.4f' % (lo, hi, np.percentile(np.abs(tqo[m]), 99), (np.abs(tqo[m]) > 0.8).mean()))
