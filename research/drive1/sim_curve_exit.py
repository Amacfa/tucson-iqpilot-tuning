#!/usr/bin/env python3
"""Closed-loop curve-exit simulation for the Tucson LatControlTorque path.

Plant: first-order lag + pure delay, lat_accel' = (K(v)*torque(t-tau) - lat_accel)/T,
fitted per drive on active frames (grid over T,tau; K by least squares per speed bin).
Controller: mirror of IQ LatControlTorque (PID in lat-accel space, speed-scheduled KP,
FF = desired + friction, torque = lat_accel/K_ctrl (+friction), Hyundai rate limits 2 up/3 down
per frame at 270 max), with optional measurement low-pass and variants.
Metric: 0.5-3 Hz band-energy fraction of torque and lat accel in the 4 s after a curve exit.
Everything is open to inspection: results printed as JSON.
"""
import json, sys
import numpy as np

DT = 0.01
INTERP_SPEEDS = [1, 1.5, 2.0, 3.0, 5, 7.5, 10, 15, 30]
KP_INTERP = [250, 120, 65, 30, 11.5, 5.5, 3.5, 2.0, 0.8]
KI = 0.15
FRICTION_THRESHOLD = 0.3
STEER_MAX = 270
RATE_UP, RATE_DOWN = 2, 3


def band_fraction(x, lo=0.5, hi=3.0):
  x = np.asarray(x) - np.mean(x)
  if len(x) < 32 or np.allclose(x, 0):
    return 0.0
  X = np.abs(np.fft.rfft(x)) ** 2
  f = np.fft.rfftfreq(len(x), DT)
  tot = X[f > 0.05].sum()
  return float(X[(f >= lo) & (f <= hi)].sum() / tot) if tot > 0 else 0.0


def fit_plant(v, tq, la, ok, bins=((3, 6), (6, 9), (9, 13), (13, 18), (18, 30))):
  """Grid-fit T,tau globally; per-bin K by LS. Returns dict."""
  best = None
  for T in (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0, 1.3):
    for tau in (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4):
      d = int(round(tau / DT))
      a = DT / T
      # simulate unit-gain plant response to torque, then LS gain per bin
      y = np.zeros_like(tq)
      src = np.concatenate([np.zeros(d), tq[:len(tq) - d]]) if d else tq
      for k in range(1, len(tq)):
        y[k] = y[k - 1] + a * (src[k] - y[k - 1])
      Ks, sse = {}, 0.0
      for lo, hi in bins:
        m = ok & (v >= lo) & (v < hi) & (np.abs(y) > 0.02)
        if m.sum() < 200:
          continue
        K = float(np.dot(y[m], la[m]) / np.dot(y[m], y[m]))
        Ks[f"{lo}-{hi}"] = (K, int(m.sum()))
        sse += float(((la[m] - K * y[m]) ** 2).sum())
      if Ks and (best is None or sse < best["sse"]):
        best = {"T": T, "tau": tau, "K": Ks, "sse": sse}
  return best


class Controller:
  def __init__(self, kp_scale=0.8, friction_scale=0.7, friction=0.12, meas_tau=0.0,
               factor_table=([8.0, 15.0, 25.0], [2.95, 3.35, 3.70]), kp_lowspeed_scale=1.0,
               steer_delay=0.1):
    self.kp = [g * kp_scale for g in KP_INTERP]
    self.kp_low = kp_lowspeed_scale
    self.fs, self.fric = friction_scale, friction
    self.meas_tau = meas_tau
    self.table = factor_table
    self.i = 0.0
    self.meas_f = None
    self.delay_frames = int(steer_delay / DT) + 1
    self.buf = [0.0] * 100
    self.last_tq270 = 0.0

  def factor(self, v):
    return float(np.interp(v, *self.table))

  def step(self, v, desired, measurement, active_prev):
    if self.meas_tau > 0:
      if self.meas_f is None:
        self.meas_f = measurement
      alpha = DT / (self.meas_tau + DT)
      self.meas_f += alpha * (measurement - self.meas_f)
      fb = self.meas_f
    else:
      fb = measurement
    self.buf.append(desired); self.buf.pop(0)
    setpoint = self.buf[-self.delay_frames]
    error = setpoint - fb
    kp = float(np.interp(v, INTERP_SPEEDS, self.kp))
    if v < 10:
      kp *= self.kp_low
    fric = self.fs * self.fric * float(np.interp(error, [-FRICTION_THRESHOLD, FRICTION_THRESHOLD], [-1, 1]))
    K = self.factor(v)
    ff = desired  # lat-accel space; friction added in torque space below like torque_from_lateral_accel
    p = kp * error
    if v >= 5:
      self.i += KI * error * DT
    out_la = p + self.i + ff
    tq = out_la / K + fric
    tq = float(np.clip(tq, -1, 1))
    # Hyundai rate limit in 270 units
    t270 = tq * STEER_MAX
    if abs(t270) > abs(self.last_tq270) or np.sign(t270) != np.sign(self.last_tq270):
      t270 = np.clip(t270, self.last_tq270 - RATE_UP, self.last_tq270 + RATE_UP)
    else:
      t270 = np.clip(t270, self.last_tq270 - RATE_DOWN, self.last_tq270 + RATE_DOWN)
    self.last_tq270 = t270
    return t270 / STEER_MAX, p, self.i, ff


def simulate(v, desired, plant, ctrl, la0, tq0):
  n = len(v)
  la = np.zeros(n); tq = np.zeros(n)
  la[0] = la0; ctrl.last_tq270 = tq0 * STEER_MAX; ctrl.i = 0.0
  d = int(round(plant["tau"] / DT)); a = DT / plant["T"]
  for k in range(1, n):
    tq[k - 1], _, _, _ = ctrl.step(v[k - 1], desired[k - 1], la[k - 1], True)
    src = tq[max(k - 1 - d, 0)]
    Kv = plant_K(plant, v[k])
    la[k] = la[k - 1] + a * (Kv * src - la[k - 1])
  return la, tq


def plant_K(plant, v):
  keys = sorted(plant["K"], key=lambda s: float(s.split("-")[0]))
  mids = [(float(k.split("-")[0]) + float(k.split("-")[1])) / 2 for k in keys]
  vals = [plant["K"][k][0] for k in keys]
  return float(np.interp(v, mids, vals))


def main(npz_path):
  d = np.load(npz_path, allow_pickle=True)
  v, la, tq = d["vEgo"], d["ala"], -d["tqo"]
  des, act = d["dla"], d["act"].astype(bool)
  pressed = d["prs"].astype(bool)
  seg = d["seg"]; t = d["t"]
  W = 300
  ok = act & ~pressed & (v > 3)
  plant = fit_plant(v, tq, la, ok)
  print("PLANT", json.dumps(plant))
  # curve exits: |des|>0.8 then <0.3, 4 s window, no steer pressed
  exits = []
  for s in np.unique(seg):
    idx = np.where(seg == s)[0]
    dd = np.abs(des[idx]); above = dd > 0.8
    last_above = -10**9
    for k in range(100, len(idx) - W):
      e = idx[k]
      if above[k]:
        last_above = k
      if not (dd[k] < 0.3 and dd[k - 1] >= 0.3 and k - last_above < 300):
        continue
      contiguous = np.all(np.diff(t[e - 100:e + W]) < 0.03)
      if contiguous and not pressed[e:e + W].any() and act[e:e + W].all():
        exits.append(e)
  exits = [e for i, e in enumerate(exits) if i == 0 or e - exits[i - 1] > W]
  print("EXITS", len(exits))
  variants = {
    "v1_filter60ms": dict(meas_tau=0.06),
    "v2_nofilter": dict(),
    "v2_lowspeed_factor_fit": dict(factor_table=([8.0, 15.0, 25.0], [max(plant_K(plant, 6), 2.0), 3.35, 3.70])),
    "v2_kp_low_x0.6": dict(kp_lowspeed_scale=0.6),
    "v2_kp_low_x0.6_factor_fit": dict(kp_lowspeed_scale=0.6, factor_table=([8.0, 15.0, 25.0], [max(plant_K(plant, 6), 2.0), 3.35, 3.70])),
    "v2_filter30ms": dict(meas_tau=0.03),
    "v1_filter60ms_delay0.3": dict(meas_tau=0.06, steer_delay=0.3),
    "v2_nofilter_delay0.3": dict(steer_delay=0.3),
    "v2_nofilter_delay0.15": dict(steer_delay=0.15),
    "v2_kp_low_x0.6_delay0.3": dict(kp_lowspeed_scale=0.6, steer_delay=0.3),
  }
  res = {}
  for name, kw in variants.items():
    ftq, fla, rms = [], [], []
    for e in exits:
      sl = slice(e - 100, e + W)
      c = Controller(**kw)
      la_s, tq_s = simulate(v[sl], des[sl], plant, c, la[e - 100], tq[e - 100])
      ftq.append(band_fraction(tq_s[100:])); fla.append(band_fraction(la_s[100:]))
      rms.append(float(np.std(np.diff(tq_s[100:])) * STEER_MAX))
    res[name] = {"band_frac_torque": round(float(np.mean(ftq)), 3), "band_frac_lataccel": round(float(np.mean(fla)), 3),
                 "dither_x270": round(float(np.mean(rms)), 2)}
  # logged (real) reference
  ftq = [band_fraction(tq[e:e + W]) for e in exits]; fla = [band_fraction(la[e:e + W]) for e in exits]
  res["exit_speeds"] = [round(float(v[e]), 1) for e in exits]
  res["logged_drive1"] = {"band_frac_torque": round(float(np.mean(ftq)), 3), "band_frac_lataccel": round(float(np.mean(fla)), 3)}
  print("RESULTS", json.dumps(res, indent=1))


if __name__ == "__main__":
  main(sys.argv[1])
