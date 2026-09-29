"""Quantify the release-3736edc Hyundai longitudinal change: PID error = speeds[0]-vEgo (kp=1, kf=1)
instead of aTarget-aEgo.  Reconstruct P term as acc - cc_at while longControlState==pid and unsaturated.
Compare with what the old accel-error P term (cc_at - aEgo) would have been on the same frames."""
import gzip, json, glob, sys
import numpy as np

routes = sys.argv[1:] or ['00000024', '00000025', '00000026', '00000027', '00000028', '00000029', '0000002a']
rows = []
for r in routes:
  for f in sorted(glob.glob(f'/home/ubuntu/tucson/drives/export/{r}--*.jsonl.gz')):
    for i, l in enumerate(gzip.open(f, 'rt')):
      if i == 0: continue
      d = json.loads(l)
      if d.get('lon') != 1 or 'acc' not in d or 'lp_at' not in d: continue
      rows.append((d['t'], d['v'], d['a'], d['acc'], d.get('lp_at', 0.0), d.get('lcs', ''), d.get('gas', 0), d.get('brk', 0), d.get('sstop', 0), d.get('lper', ''), f[-30:-9]))
n = len(rows)
lcs = np.array([x[5] for x in rows]); v = np.array([x[1] for x in rows]); a = np.array([x[2] for x in rows])
acc = np.array([x[3] for x in rows]); at = np.array([x[4] for x in rows]); sstop = np.array([x[8] for x in rows])
pid = (lcs == 'pid') & (sstop == 0)
p_speed = acc - at                 # = kp*(v0 - vEgo) in pid state, kf=1
p_accel = at - a                   # what the old error would have been
unsat = pid & (np.abs(acc) < 1.9)
print(f'frames long-active {n}  pid&!shouldStop {pid.sum()}  unsat {unsat.sum()}  ({unsat.sum()/100:.0f} s)')
def q(x): return np.round(np.percentile(x, [5, 25, 50, 75, 95]), 3)
print('speed-error P (acc - aTarget)   p5/25/50/75/95:', q(p_speed[unsat]), ' rms', round(float(np.sqrt(np.mean(p_speed[unsat]**2))), 3))
print('accel-error P (aTarget - aEgo)  p5/25/50/75/95:', q(p_accel[unsat]), ' rms', round(float(np.sqrt(np.mean(p_accel[unsat]**2))), 3))
print('corr(p_speed, p_accel) =', round(float(np.corrcoef(p_speed[unsat], p_accel[unsat])[0, 1]), 3))
print('fraction of |acc| explained: |P|/|acc| median', round(float(np.median(np.abs(p_speed[unsat]) / np.maximum(np.abs(acc[unsat]), 0.05))), 3))
for lo, hi in [(0, 1), (1, 3), (3, 8), (8, 15), (15, 40)]:
  m = unsat & (v >= lo) & (v < hi)
  if m.sum() < 50: continue
  print(f'  v {lo:2d}-{hi:2d} m/s n={m.sum():6d}  P_speed rms {np.sqrt(np.mean(p_speed[m]**2)):.3f} mean {p_speed[m].mean():+.3f} | P_accel rms {np.sqrt(np.mean(p_accel[m]**2)):.3f} | aTarget rms {np.sqrt(np.mean(at[m]**2)):.3f}')
# launches: pid state, v crossing 0.3 -> 3 m/s, look at P during the first 2 s
t = np.array([x[0] for x in rows]); seg = np.array([x[10] for x in rows])
launch = []
for k in range(1, n):
  if seg[k] == seg[k-1] and v[k-1] < 0.3 <= v[k] and lcs[k] == 'pid':
    w = (seg == seg[k]) & (t >= t[k]) & (t < t[k] + 2.0) & pid
    if w.sum() > 100:
      launch.append((seg[k], round(t[k], 1), round(float(p_speed[w].mean()), 3), round(float(p_speed[w].max()), 3), round(float(at[w].mean()), 3), round(float(acc[w].max()), 3), round(float(a[w].max()), 3)))
print('launches (seg, t, P_speed mean, P max, aTarget mean, acc max, aEgo max):')
for x in launch: print('  ', x)
# stops: pid state with shouldStop==0, last 3 s before v<0.5 while decelerating
stops = []
for k in range(1, n):
  if seg[k] == seg[k-1] and v[k-1] >= 0.5 > v[k]:
    w = (seg == seg[k]) & (t >= t[k] - 3.0) & (t < t[k]) & (lcs == 'pid')
    if w.sum() > 100:
      stops.append((seg[k], round(t[k], 1), int((w & (sstop == 1)).sum()), round(float(p_speed[w & (sstop == 0)].mean()) if (w & (sstop == 0)).sum() else float('nan'), 3), round(float(acc[w].min()), 3), round(float(at[w].min()), 3), round(float(a[w].min()), 3)))
print('stops (seg, t, frames in settle, P_speed mean(pid part), acc min, aTarget min, aEgo min):')
for x in stops: print('  ', x)
