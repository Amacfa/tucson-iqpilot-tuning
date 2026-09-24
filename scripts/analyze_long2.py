import numpy as np, json, gzip, glob, collections
A = np.load('/home/ubuntu/tucson/drives/all_frames.npy'); C = json.load(open('/home/ubuntu/tucson/drives/all_frames_cols.json'))
ix = {c: i for i, c in enumerate(C)}
def col(n): return A[:, ix[n]]
rid, seg, t = col('rid'), col('seg'), col('t'); T = seg * 60 + t
v, a, acc, lon, en, cen, gas, brk, ss, lat = [col(n) for n in 'v a acc lon en cen gas brk ss lat'.split()]

def blocks_of(mask, min_len=1):
    idx = np.flatnonzero(mask); out = []
    if not len(idx): return out
    s = p = idx[0]
    for i in idx[1:]:
        if i != p + 1 or rid[i] != rid[p]:
            if p - s + 1 >= min_len: out.append((s, p + 1))
            s = i
        p = i
    if p - s + 1 >= min_len: out.append((s, p + 1))
    return out

print('== per-route long usage')
for r in np.unique(rid):
    m = rid == r
    print(' %08x: %5.1f min total, long-active %5.1f min, lat-only %5.1f min, gas-ovr-while-long %3d' % (int(r), m.sum() / 6000, (m & (lon == 1)).sum() / 6000, (m & (lat == 1) & (lon == 0)).sum() / 6000,
          len(blocks_of(m & (gas == 1) & (np.roll(lon, 1) == 1), 20))))

# gas overrides that start while long was active in the preceding second
go = blocks_of((gas == 1) & (en == 1), 20)
rows = []
for s, e in go:
    if s < 100 or rid[s - 100] != rid[s]: continue
    if lon[s - 100:s].mean() < 0.9: continue
    pre_cmd = acc[s - 100:s]; pre_a = a[s - 100:s]
    rows.append([v[s], pre_cmd.mean(), pre_a.mean(), (e - s) / 100, v[min(e, len(A) - 1)] - v[s], acc[s - 300:s].max(), (pre_cmd < 0.05).mean()])
R = np.array(rows)
print('\n== gas overrides starting from long-active: %d  (%.1f / long-hour)' % (len(R), len(R) / (lon.sum() / 360000)))
print(' v median %.1f | cmd(1s before) median %.2f p25 %.2f p75 %.2f | actual before %.2f | dur %.1fs | dv %.1f | max cmd in 3s before %.2f | frac cmd<0.05 %.2f' % (
    np.median(R[:, 0]), np.median(R[:, 1]), *np.percentile(R[:, 1], [25, 75]), np.median(R[:, 2]), np.median(R[:, 3]), np.median(R[:, 4]), np.median(R[:, 5]), np.median(R[:, 6])))
for lo, hi in [(0, 1), (1, 5), (5, 10), (10, 15), (15, 20), (20, 40)]:
    m = (R[:, 0] >= lo) & (R[:, 0] < hi)
    if m.sum(): print('  v %2d-%2d: n=%3d cmd before %.2f actual before %.2f dur %.1f dv %.1f' % (lo, hi, m.sum(), np.median(R[m, 1]), np.median(R[m, 2]), np.median(R[m, 3]), np.median(R[m, 4])))
# what does the driver do: how hard does the driver accelerate during override vs what op was commanding
dur_a = []
for s, e in go:
    if s < 100 or lon[s - 100:s].mean() < 0.9: continue
    dur_a.append(a[s:e].mean())
print(' driver accel during override: median %.2f p75 %.2f (vs op cmd before %.2f)' % (np.median(dur_a), np.percentile(dur_a, 75), np.median(R[:, 1])))

# positive accel step response: cmd rises by >0.5 within 1s from <0.2 ; how does actual follow
steps = []
i = 200
cmd_s = np.convolve(acc, np.ones(10) / 10, 'same')
while i < len(A) - 400:
    if lon[i] == 1 and lon[i - 100] == 1 and lon[i + 300] == 1 and rid[i - 100] == rid[i + 300] and cmd_s[i - 100] < 0.2 and cmd_s[i] > 0.7 and gas[i - 100:i + 300].sum() == 0 and v[i] > 3:
        steps.append([v[i], cmd_s[i:i + 300].max(), a[i:i + 300].max(), (np.flatnonzero(a[i:i + 300] > 0.5 * cmd_s[i:i + 300].max())[0] / 100) if (a[i:i + 300] > 0.5 * cmd_s[i:i + 300].max()).any() else np.nan, a[i + 100:i + 300].mean() / max(cmd_s[i + 100:i + 300].mean(), 0.1)])
        i += 300
    i += 1
S = np.array(steps)
print('\n== positive accel steps (cmd <0.2 -> >0.7):', len(S))
if len(S): print(' v median %.1f | cmd peak %.2f | actual peak %.2f | t to 50%% %.2fs | ratio actual/cmd in 1-3s window median %.2f p25 %.2f' % (np.median(S[:, 0]), np.median(S[:, 1]), np.median(S[:, 2]), np.nanmedian(S[:, 3]), np.median(S[:, 4]), np.percentile(S[:, 4], 25)))
steps = []
i = 200
while i < len(A) - 400:
    if lon[i] == 1 and lon[i - 100] == 1 and lon[i + 300] == 1 and rid[i - 100] == rid[i + 300] and cmd_s[i - 100] > -0.2 and cmd_s[i] < -0.7 and brk[i - 100:i + 300].sum() == 0 and v[i] > 3:
        steps.append([v[i], cmd_s[i:i + 300].min(), a[i:i + 300].min(), (np.flatnonzero(a[i:i + 300] < 0.5 * cmd_s[i:i + 300].min())[0] / 100) if (a[i:i + 300] < 0.5 * cmd_s[i:i + 300].min()).any() else np.nan, a[i + 100:i + 300].mean() / min(cmd_s[i + 100:i + 300].mean(), -0.1)])
        i += 300
    i += 1
S = np.array(steps)
print('== negative accel steps (cmd >-0.2 -> <-0.7):', len(S))
if len(S): print(' v median %.1f | cmd min %.2f | actual min %.2f | t to 50%% %.2fs | ratio 1-3s median %.2f p25 %.2f' % (np.median(S[:, 0]), np.median(S[:, 1]), np.median(S[:, 2]), np.nanmedian(S[:, 3]), np.median(S[:, 4]), np.percentile(S[:, 4], 25)))

# stop detail: profile of last 4 seconds before standstill (mean over stops)
prof = []
for i in np.flatnonzero((ss[1:] == 1) & (ss[:-1] == 0) & (lon[:-1] == 1)) + 1:
    if i < 400 or rid[i - 400] != rid[i] or brk[i - 400:i].any(): continue
    prof.append(np.stack([a[i - 400:i], acc[i - 400:i], v[i - 400:i]]))
P = np.array(prof)
print('\n== stop profile (n=%d, no brake), t before standstill: mean actual a / mean cmd / mean v' % len(P))
for k in [400, 300, 200, 150, 100, 70, 50, 30, 20, 10, 1]:
    print('  -%.1fs: a %.2f cmd %.2f v %.2f' % (k / 100, P[:, 0, -k].mean(), P[:, 1, -k].mean(), P[:, 2, -k].mean()))
# standstill: does it creep / hold; time held; resume behavior
# cruise hold noise vs road: correlation of accel noise with cmd
m3 = (lon == 1) & (v > 15) & (np.abs(acc) < 0.3)
print('\n== cruise-hold: corr(cmd, actual+0.6s) %.2f' % np.corrcoef(acc[np.flatnonzero(m3)[:-60]], a[np.flatnonzero(m3)[:-60] + 60])[0, 1])
# accel command quantization / dither: distribution of |d cmd| per frame
d = np.abs(np.diff(acc))[(lon[1:] == 1) & (lon[:-1] == 1)]
print(' |dcmd| per 10ms frame: frac==0 %.2f, frac<0.01 %.2f, frac>0.05 %.3f, frac>0.2 %.4f' % ((d == 0).mean(), (d < 0.01).mean(), (d > 0.05).mean(), (d > 0.2).mean()))
# command update cadence (planner is 20Hz): does cmd change every frame or every 5?
ch = (np.diff(acc) != 0)[(lon[1:] == 1) & (lon[:-1] == 1)]
print(' cmd changes on %.1f%% of frames' % (100 * ch.mean()))
# events summary from meta for long faults
ev = collections.Counter(); per_route = collections.defaultdict(collections.Counter)
for f in sorted(glob.glob('/home/ubuntu/tucson/drives/export/*.jsonl.gz')):
    m = json.loads(gzip.open(f, 'rt').readline())['meta']; r = f.split('/')[-1][:8]
    last = None
    for tt, w, names in m['events']:
        if w != 'onroadEvents': continue
        for n in names:
            if n in ('cruiseMismatch', 'accFaulted', 'fcw', 'controlsMismatch', 'resumeBlocked', 'gasPressedOverride', 'steerSaturated'):
                per_route[n][r] += 1
for n, c in per_route.items(): print(' event', n, dict(sorted(c.items())))
