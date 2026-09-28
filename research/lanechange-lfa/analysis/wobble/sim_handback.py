"""Closed-loop hand-back simulator (directional).
Plant: torque -> lat accel, 2nd-order (K, wn, zeta) + delay, plus Hyundai actuator rate limits (2 up / 3 down per 10 ms, /270).
Controller: replica of v2 latcontrol_torque (speed-scheduled P x0.8, KI 0.15, friction relay x0.7 in torque units,
delayed request-buffer FF, JERK_GAIN 0.3), with switchable candidates.
Excitation: the real requested lat-accel (actuators.curvature * v^2) from route 0x26 seg 6, 36-48 s (lane change + hand-back at 38.63 s).
"""
import gzip, json, sys
import numpy as np

SEG = '/home/ubuntu/tucson/drives/export/00000026--84c8b1874d--6.jsonl.gz'
DT = 0.01
INTERP_SPEEDS = [1, 1.5, 2.0, 3.0, 5, 7.5, 10, 15, 30]
KP_INTERP = [250, 120, 65, 30, 11.5, 5.5, 3.5, 2.0, 0.8]
KI = 0.15
FRICTION = 0.12
FRICTION_THRESHOLD = 0.3
JERK_GAIN = 0.3
LAT_DELAY = 0.3
LAF_TABLE = ([8.0, 15.0, 25.0], [2.95, 3.35, 3.70])
RATE_UP = 2 / 270 / 0.01
RATE_DOWN = 3 / 270 / 0.01


def load_excitation():
  rows = []
  with gzip.open(SEG, 'rt') as g:
    g.readline()
    for l in g:
      r = json.loads(l)
      if 36.0 <= r['t'] <= 48.0 and r.get('lat') is not None:
        rows.append(r)
  t = np.array([r['t'] for r in rows]); v = np.array([r['v'] for r in rows])
  fut = np.array([r['curv'] for r in rows]) * v * v
  ala = np.array([r['ala'] for r in rows]); tqo = np.array([r['tqo'] for r in rows])
  act = np.array([1 if r['lat'] else 0 for r in rows]); prs = np.array([r['prs'] for r in rows])
  tu = np.arange(t[0], t[-1], DT)
  return tu, np.interp(tu, t, fut), np.interp(tu, t, v), np.interp(tu, t, ala), np.interp(tu, t, tqo), np.interp(tu, t, prs) > 0.5, np.interp(tu, t, act) > 0.5


class Plant:
  def __init__(self, K, wn, zeta, tau):
    self.K, self.wn, self.z = K, wn, zeta
    self.buf = [0.0] * max(1, int(round(tau / DT)))
    self.x = 0.0; self.xd = 0.0
    self.tq_applied = 0.0

  def step(self, tq_req):
    # actuator rate limit toward request (Hyundai: 2 up, 3 down per frame, in |torque| terms)
    d = tq_req - self.tq_applied
    if abs(tq_req) >= abs(self.tq_applied):
      lim = RATE_UP * DT
    else:
      lim = RATE_DOWN * DT
    self.tq_applied += np.clip(d, -lim, lim)
    self.buf.append(self.tq_applied); u = self.buf.pop(0)
    xdd = self.K * self.wn ** 2 * u - 2 * self.z * self.wn * self.xd - self.wn ** 2 * self.x
    self.xd += xdd * DT; self.x += self.xd * DT
    return self.x, self.tq_applied

  def set_state(self, ala, tq):
    self.x = ala; self.xd = 0.0; self.tq_applied = tq; self.buf = [tq] * len(self.buf)


def run(cfg, plant_p, seed_from_data=True):
  t, fut, v, ala_real, tqo_real, prs, act = load_excitation()
  n = len(t)
  plant = Plant(**plant_p)
  buf = [0.0] * int(1.0 / DT)
  i_term = 0.0
  err_lp = 0.0
  ala = 0.0; tq_applied = 0.0
  handback_t = None
  out = dict(t=t, ala=np.zeros(n), tq=np.zeros(n), tqa=np.zeros(n), err=np.zeros(n), set=np.zeros(n), v=v, fut=fut, prs=prs)
  prev_fut = fut[0]
  for k in range(n):
    vk = v[k]
    laf = np.interp(vk, *LAF_TABLE)
    kp = np.interp(vk, INTERP_SPEEDS, KP_INTERP) * 0.8 * cfg.get('p_scale', lambda v: 1.0)(vk)
    buf.append(fut[k]); buf.pop(0)
    delay_frames = int(np.clip(LAT_DELAY / DT + 1, 1, len(buf)))
    setpoint = buf[-delay_frames]
    jerk = (fut[k] - prev_fut) / DT; prev_fut = fut[k]
    overriding = prs[k]
    if overriding:
      # driver has the wheel: plant follows the real data (we cannot model the driver); reset controller
      ala = ala_real[k]; tq_applied = tqo_real[k]
      plant.set_state(ala, tq_applied)
      i_term = 0.0; err_lp = 0.0
      handback_t = None
      out['ala'][k] = ala; out['tq'][k] = tq_applied; out['tqa'][k] = tq_applied
      continue
    if handback_t is None:
      handback_t = t[k]
    since = t[k] - handback_t
    g = 1.0
    if cfg.get('handback_ramp'):
      T, g0 = cfg['handback_ramp']
      g = g0 + (1 - g0) * min(1.0, since / T)
    err = setpoint - ala
    err_lp += (err - err_lp) * DT / cfg.get('friction_tau', 1e-9) if cfg.get('friction_tau') else 0.0
    fr_in = (err_lp if cfg.get('friction_tau') else err) + JERK_GAIN * jerk
    friction = 0.7 * FRICTION * np.clip(fr_in, -FRICTION_THRESHOLD, FRICTION_THRESHOLD) / FRICTION_THRESHOLD * laf * cfg.get('friction_scale', 1.0)
    ff = fut[k] + friction * g
    p = kp * err * g
    i_term += KI * err * DT
    i_term = np.clip(i_term, -1.0, 1.0)
    u = p + i_term + ff
    tq_req = np.clip(u / laf, -1.0, 1.0)
    if cfg.get('req_rate'):
      lim = cfg['req_rate'] * DT
      tq_req = np.clip(tq_req, tq_applied - lim, tq_applied + lim)
    ala, tq_applied = plant.step(tq_req)
    out['ala'][k] = ala; out['tq'][k] = tq_req; out['tqa'][k] = tq_applied; out['err'][k] = err; out['set'][k] = setpoint
  return out


def metrics(out, t0=43.3, t1=47.5):
  m = (out['t'] >= t0) & (out['t'] <= t1) & (~out['prs'])
  a = out['ala'][m] - np.mean(out['ala'][m])
  from scipy import signal
  f, P = signal.periodogram(a, 1 / DT)
  band = P[(f > 1.0) & (f < 3.0)].sum() / max(P[f > 0.05].sum(), 1e-12)
  return dict(ala_pp=float(np.ptp(out['ala'][m])), ala_rms=float(np.std(a)), band_1_3=float(band),
              tq_pp=float(np.ptp(out['tqa'][m])), track_rms=float(np.sqrt(np.mean((out['fut'][m] - out['ala'][m]) ** 2))))


if __name__ == '__main__':
  plant_p = json.load(open('/home/ubuntu/tucson/analysis/wobble/plant_fit.json'))
  t, fut, v, ala_real, tqo_real, prs, act = load_excitation()
  m = (t >= 43.3) & (t <= 47.5)
  print('REAL   ala_pp=%.2f ala_rms=%.2f tq_pp=%.2f' % (np.ptp(ala_real[m]), np.std(ala_real[m]), np.ptp(tqo_real[m])))
  cfgs = {
    'v2 (current)': {},
    'A: P x0.6 above 15 m/s': dict(p_scale=lambda v: np.interp(v, [12, 15], [1.0, 0.6])),
    'B: friction on LP(err, 0.3s)': dict(friction_tau=0.3),
    'C: A+B': dict(p_scale=lambda v: np.interp(v, [12, 15], [1.0, 0.6]), friction_tau=0.3),
    'D: handback ramp P/friction 0.4->1 over 1.5s': dict(handback_ramp=(1.5, 0.4)),
    'E: request rate-limit 1.0/s': dict(req_rate=1.0),
    'F: friction x0.5': dict(friction_scale=0.5),
  }
  for name, cfg in cfgs.items():
    o = run(cfg, plant_p)
    print('%-45s' % name, ' '.join('%s=%.3f' % kv for kv in metrics(o).items()))
  print('--- plant damping sensitivity (proxy for MDPS-side damping; hypothetical) ---')
  for zeta in [plant_p['zeta'], 0.6, 0.8]:
    pp = dict(plant_p); pp['zeta'] = zeta
    o = run({}, pp)
    print('zeta=%.2f v2' % zeta, ' '.join('%s=%.3f' % kv for kv in metrics(o).items()))
