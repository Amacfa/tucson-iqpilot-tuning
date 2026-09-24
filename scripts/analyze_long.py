import numpy as np, json, collections
A = np.load('/home/ubuntu/tucson/drives/all_frames.npy'); C = json.load(open('/home/ubuntu/tucson/drives/all_frames_cols.json'))
ix = {c: i for i, c in enumerate(C)}
def col(n): return A[:, ix[n]]
rid, seg, t = col('rid'), col('seg'), col('t')
v, a, acc, lon, en, cen, gas, brk, ss = [col(n) for n in 'v a acc lon en cen gas brk ss'.split()]
# absolute time per route (segments are 60s each; t is within-segment)
T = seg * 60 + t
# route boundaries
routes = np.unique(rid)
print('frames', len(A), 'routes', len(routes))
print('long active frames', int(lon.sum()), 'hours', lon.sum() / 100 / 3600)
print('enabled frames', int(en.sum()), 'lat-active w/o long', int(((col('lat') == 1) & (lon == 0)).sum()))

# Only long-active frames with contiguous sequences
def contiguous_blocks(mask, min_len=100):
    idx = np.flatnonzero(mask); blocks = []
    if len(idx) == 0: return blocks
    start = idx[0]; prev = idx[0]
    for i in idx[1:]:
        if i != prev + 1 or rid[i] != rid[prev] or T[i] - T[prev] > 0.1:
            if prev - start + 1 >= min_len: blocks.append((start, prev + 1))
            start = i
        prev = i
    if prev - start + 1 >= min_len: blocks.append((start, prev + 1))
    return blocks

blocks = contiguous_blocks(lon == 1, 300)
print('long-active blocks >=3s:', len(blocks), 'total s', sum(e - s for s, e in blocks) / 100)

# 1) command vs actual: lag via cross-correlation, gain via regression, per speed bin
lags = []; pairs = []
for s, e in blocks:
    x = acc[s:e] - acc[s:e].mean(); y = a[s:e] - a[s:e].mean()
    if x.std() < 0.05 or y.std() < 0.05: continue
    best = None
    for L in range(0, 150, 2):
        if e - s - L < 200: break
        c = np.corrcoef(x[:len(x) - L], y[L:])[0, 1]
        if best is None or c > best[1]: best = (L, c)
    if best and best[1] > 0.6: lags.append((best[0] / 100, best[1], e - s, v[s:e].mean()))
lags = np.array(lags)
print('\n== accel cmd->actual lag (blocks with corr>0.6):', len(lags))
if len(lags):
    print(' median lag %.2fs, p25 %.2f p75 %.2f, weighted mean %.2f' % (np.median(lags[:, 0]), *np.percentile(lags[:, 0], [25, 75]), np.average(lags[:, 0], weights=lags[:, 2])))
    for lo, hi in [(0, 8), (8, 15), (15, 25), (25, 40)]:
        m = (lags[:, 3] >= lo) & (lags[:, 3] < hi)
        if m.sum(): print('  v %2d-%2d m/s: n=%3d lag median %.2f corr %.2f' % (lo, hi, m.sum(), np.median(lags[m, 0]), np.median(lags[m, 1])))

# gain: actual (shifted by 0.5s) vs commanded, active frames
L = 50
m = (lon == 1)
mi = np.flatnonzero(m); mi = mi[mi + L < len(A)]
ok = (rid[mi] == rid[mi + L]) & (lon[mi + L] == 1) & (gas[mi] == 0) & (brk[mi] == 0)
mi = mi[ok]
x, y = acc[mi], a[mi + L]
print('\n== steady gain actual(t+0.5)/cmd: slope %.3f intercept %.3f (n=%d)' % (*np.polyfit(x, y, 1), len(x)))
for lo, hi in [(-3, -1.5), (-1.5, -0.7), (-0.7, -0.3), (-0.3, -0.1), (-0.1, 0.1), (0.1, 0.3), (0.3, 0.7), (0.7, 1.5), (1.5, 3)]:
    mm = (x >= lo) & (x < hi)
    if mm.sum() > 200: print('  cmd %5.1f..%5.1f: n=%6d actual median %6.3f  err median %6.3f  p90|err| %.3f' % (lo, hi, mm.sum(), np.median(y[mm]), np.median(y[mm] - x[mm]), np.percentile(np.abs(y[mm] - x[mm]), 90)))
for lo, hi in [(0, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 40)]:
    mm = (v[mi] >= lo) & (v[mi] < hi)
    if mm.sum() > 500:
        sl, ic = np.polyfit(x[mm], y[mm], 1)
        print('  v %2d-%2d: n=%6d slope %.3f int %.3f rmse %.3f' % (lo, hi, mm.sum(), sl, ic, np.sqrt(np.mean((y[mm] - x[mm]) ** 2))))

# 2) jerk / smoothness of command and actual
def diffs(sig, mask):
    d = np.diff(sig) * 100
    ok = mask[1:] & mask[:-1] & (rid[1:] == rid[:-1])
    return d[ok]
dcmd = diffs(acc, lon == 1); dact = diffs(a, lon == 1)
print('\n== command jerk (m/s^3): rms %.2f p95 %.2f p99 %.2f  max %.1f' % (np.sqrt(np.mean(dcmd ** 2)), *np.percentile(np.abs(dcmd), [95, 99]), np.abs(dcmd).max()))
print('   actual jerk (m/s^3, aEgo diff): rms %.2f p95 %.2f p99 %.2f' % (np.sqrt(np.mean(dact ** 2)), *np.percentile(np.abs(dact), [95, 99])))
# smoothed actual jerk (0.5s window)
k = np.ones(50) / 50
asm = np.convolve(a, k, 'same'); dsm = diffs(asm, lon == 1)
print('   actual jerk 0.5s-smoothed: rms %.2f p95 %.2f p99 %.2f' % (np.sqrt(np.mean(dsm ** 2)), *np.percentile(np.abs(dsm), [95, 99])))

# 3) stops: transitions to standstill while long active
stops = []
for i in np.flatnonzero((ss[1:] == 1) & (ss[:-1] == 0) & (lon[:-1] == 1)) + 1:
    s = max(0, i - 800)
    if rid[s] != rid[i]: continue
    seg_a = a[s:i]; seg_acc = acc[s:i]; seg_v = v[s:i]
    # approach: min accel in last 8s, accel in last 1s, cmd in last 1s, decel rate (a vs v) in 5-1 m/s band
    stops.append(dict(rid=int(rid[i]), T=float(T[i]), min_a=float(seg_a.min()), min_cmd=float(seg_acc.min()), a_last1=float(seg_a[-100:].mean()), cmd_last1=float(seg_acc[-100:].mean()),
                      a_last03=float(seg_a[-30:].min()), v_8s_ago=float(seg_v[0]), jerk_last2=float(np.abs(np.diff(np.convolve(seg_a[-200:], np.ones(20) / 20, 'same'))).max() * 100)))
print('\n== stops under long control:', len(stops))
if stops:
    S = {k: np.array([d[k] for d in stops]) for k in stops[0]}
    print(' min accel in approach: median %.2f p10 %.2f ; min cmd median %.2f p10 %.2f' % (np.median(S['min_a']), np.percentile(S['min_a'], 10), np.median(S['min_cmd']), np.percentile(S['min_cmd'], 10)))
    print(' final 1s actual accel median %.2f (cmd %.2f); final 0.3s min accel median %.2f p10 %.2f  (head-nod proxy)' % (np.median(S['a_last1']), np.median(S['cmd_last1']), np.median(S['a_last03']), np.percentile(S['a_last03'], 10)))
    print(' peak smoothed jerk in last 2s: median %.2f p90 %.2f' % (np.median(S['jerk_last2']), np.percentile(S['jerk_last2'], 90)))

# 4) launches from standstill under long
launches = []
for i in np.flatnonzero((ss[1:] == 0) & (ss[:-1] == 1) & (lon[1:] == 1)) + 1:
    e = min(len(A), i + 600)
    if rid[e - 1] != rid[i] or gas[i:e].any(): continue
    tt = T[i:e] - T[i]; vv = v[i:e]
    t_to_3 = tt[vv >= 3][0] if (vv >= 3).any() else np.nan
    launches.append(dict(cmd_first1=float(acc[i:i + 100].mean()), a_first2=float(a[i:i + 200].mean()), a_peak=float(a[i:e].max()), cmd_peak=float(acc[i:e].max()), t_to_3=float(t_to_3), lag=float(tt[a[i:e] > 0.3][0]) if (a[i:e] > 0.3).any() else np.nan))
print('\n== launches from standstill under long (no gas):', len(launches))
if launches:
    L_ = {k: np.array([d[k] for d in launches]) for k in launches[0]}
    print(' cmd first 1s median %.2f; actual first 2s median %.2f; peak actual median %.2f (cmd peak %.2f); time to 3 m/s median %.1fs; time until a>0.3 median %.2fs' % (
        np.median(L_['cmd_first1']), np.median(L_['a_first2']), np.median(L_['a_peak']), np.median(L_['cmd_peak']), np.nanmedian(L_['t_to_3']), np.nanmedian(L_['lag'])))

# 5) driver gas overrides during long: how often, what was commanded, speed
go = (gas == 1) & (en == 1)
gob = contiguous_blocks(go, 20)
print('\n== gas override episodes (>0.2s) while enabled:', len(gob), 'per hour of enabled %.1f' % (len(gob) / (en.sum() / 100 / 3600)))
if gob:
    pre = np.array([[v[s], acc[max(0, s - 50):s].mean(), a[max(0, s - 50):s].mean(), (e - s) / 100, v[e - 1] - v[s]] for s, e in gob])
    print(' at speed median %.1f m/s; cmd before median %.2f; actual before %.2f; duration median %.1fs; dv median %.1f' % tuple(np.median(pre, 0)))
    for lo, hi in [(0, 3), (3, 10), (10, 20), (20, 40)]:
        m2 = (pre[:, 0] >= lo) & (pre[:, 0] < hi)
        if m2.sum(): print('  v %2d-%2d: n=%3d cmd before %.2f dur %.1f' % (lo, hi, m2.sum(), np.median(pre[m2, 1]), np.median(pre[m2, 3])))
# brake overrides
bo = (brk == 1) & (en == 1)
bob = contiguous_blocks(bo, 20)
print('== brake override episodes while enabled:', len(bob))
if bob:
    pre = np.array([[v[s], acc[max(0, s - 50):s].mean(), a[max(0, s - 50):s].mean(), (e - s) / 100] for s, e in bob])
    print(' at speed median %.1f; cmd before median %.2f (p10 %.2f); actual before %.2f; dur %.1fs' % (np.median(pre[:, 0]), np.median(pre[:, 1]), np.percentile(pre[:, 1], 10), np.median(pre[:, 2]), np.median(pre[:, 3])))

# 6) speed hold quality: cruising (|cmd|<0.3, v>15) accel noise
m3 = (lon == 1) & (v > 15) & (np.abs(acc) < 0.3)
print('\n== cruise hold (v>15, |cmd|<0.3): frames %d, actual accel std %.3f, cmd std %.3f' % (m3.sum(), a[m3].std(), acc[m3].std()))
# command oscillation: sign changes per minute of d(cmd)
d = np.diff(acc); okm = (lon[1:] == 1) & (lon[:-1] == 1)
sgn = np.sign(d[okm]); sgn = sgn[sgn != 0]
print(' cmd derivative sign changes / min: %.1f' % ((np.diff(sgn) != 0).sum() / (okm.sum() / 6000)))
# power spectrum of cmd in long blocks
ps = np.zeros(0); n = 0
for s, e in blocks:
    if e - s < 2000: continue
    x = acc[s:e] - acc[s:e].mean(); f = np.fft.rfftfreq(len(x), 0.01); P = np.abs(np.fft.rfft(x)) ** 2
    b = [(f < 0.2), (f >= 0.2) & (f < 0.5), (f >= 0.5) & (f < 1.5), (f >= 1.5)]
    ps = ps + np.array([P[bb].sum() for bb in b]) if len(ps) else np.array([P[bb].sum() for bb in b]); n += 1
if n: print(' cmd power fractions <0.2Hz %.3f 0.2-0.5 %.3f 0.5-1.5 %.3f >1.5 %.3f (over %d blocks)' % (*(ps / ps.sum()), n))
