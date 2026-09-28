"""Fit torque->lat-accel plant (2nd order + delay) to closed-loop FRF estimate from v2 frames (15-22 m/s).
Closed-loop identification is biased; used as a directional model only."""
import numpy as np, json
from scipy import signal, optimize

z = np.load('/home/ubuntu/tucson/analysis/wobble/v2_frames.npz', allow_pickle=True)


def frf(z, vlo, vhi, nper=512):
  fs = 100.0
  X = []; Y = []
  for seg in np.unique(z['seg']):
    m = (z['seg'] == seg)
    t = z['t'][m]; v = z['vEgo'][m]; tqo = z['tqo'][m]; ala = z['ala'][m]; prs = z['prs'][m]
    ok = (v > vlo) & (v < vhi) & (prs == 0)
    idx = np.where(ok)[0]
    if len(idx) < 400:
      continue
    breaks = np.where((np.diff(idx) > 1) | (np.diff(t[idx]) > 0.05))[0]
    starts = np.r_[0, breaks + 1]; ends = np.r_[breaks + 1, len(idx)]
    for s, e in zip(starts, ends):
      if e - s < 800:
        continue
      ii = idx[s:e]
      tt = t[ii]; tu = np.arange(tt[0], tt[-1], 0.01)
      X.append(np.interp(tu, tt, -tqo[ii])); Y.append(np.interp(tu, tt, ala[ii]))
  Pxx = 0; Pxy = 0; Pyy = 0
  for x, y in zip(X, Y):
    x = signal.detrend(x); y = signal.detrend(y)
    f, pxx = signal.csd(x, x, fs, nperseg=nper); _, pxy = signal.csd(x, y, fs, nperseg=nper); _, pyy = signal.csd(y, y, fs, nperseg=nper)
    Pxx = Pxx + pxx * len(x); Pxy = Pxy + pxy * len(x); Pyy = Pyy + pyy * len(x)
  H = Pxy / Pxx; coh = (np.abs(Pxy) ** 2 / (Pxx * Pyy)).real
  return f, H, coh, sum(len(x) for x in X) / fs


def model(p, f):
  K, wn, zeta, tau = p
  s = 1j * 2 * np.pi * f
  return K * wn ** 2 / (s ** 2 + 2 * zeta * wn * s + wn ** 2) * np.exp(-s * tau)


if __name__ == '__main__':
  f, H, coh, secs = frf(z, 15, 22)
  sel = (f >= 0.2) & (f <= 2.6)
  w = coh[sel]

  def cost(p):
    Hm = model(p, f[sel])
    return np.sum(w * np.abs(np.log(Hm / H[sel])) ** 2)
  best = None
  for wn0 in [6, 8, 10, 12]:
    for z0 in [0.1, 0.3, 0.6]:
      r = optimize.minimize(cost, [3.0, wn0, z0, 0.1], bounds=[(1, 8), (3, 20), (0.05, 1.5), (0.0, 0.3)])
      if best is None or r.fun < best.fun:
        best = r
  K, wn, zeta, tau = best.x
  print(f'data {secs:.0f}s; fit K={K:.2f} wn={wn:.2f} rad/s ({wn/2/np.pi:.2f} Hz) zeta={zeta:.2f} tau={tau:.3f}s cost={best.fun:.2f}')
  for fi in [0.4, 0.8, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5]:
    k = np.argmin(abs(f - fi)); Hm = model(best.x, f[k])
    print(f'  f={f[k]:.2f} |H|={abs(H[k]):5.2f} fit={abs(Hm):5.2f}  ph={np.degrees(np.angle(H[k])):7.1f} fit={np.degrees(np.angle(Hm)):7.1f} coh={coh[k]:.2f}')
  json.dump(dict(K=K, wn=wn, zeta=zeta, tau=tau), open('/home/ubuntu/tucson/analysis/wobble/plant_fit.json', 'w'))
