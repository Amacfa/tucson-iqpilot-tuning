#!/usr/bin/env python3
"""Per-route steering quality analysis over export_drive_summary.py output."""
import glob, gzip, json, os, sys, math
from collections import defaultdict
import numpy as np

SRC = sys.argv[1] if len(sys.argv) > 1 else '/home/ubuntu/tucson/drives/export'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/home/ubuntu/tucson/drives/analysis.json'
STEER_MAX = 270.0

def load(path):
  with gzip.open(path, 'rt') as f:
    meta = json.loads(f.readline())['meta']
    rows = [json.loads(l) for l in f if l.strip()]
  return meta, rows

def band_power(x, fs, lo, hi):
  if len(x) < 64: return 0.0
  x = np.asarray(x) - np.mean(x)
  sp = np.abs(np.fft.rfft(x)) ** 2
  fr = np.fft.rfftfreq(len(x), 1 / fs)
  tot = sp[fr > 0.05].sum()
  return float(sp[(fr >= lo) & (fr < hi)].sum() / tot) if tot > 0 else 0.0

def seg_stats(rows):
  t = np.array([r['t'] for r in rows])
  if len(t) < 2: return None
  dt = np.median(np.diff(t)); fs = 1 / dt if dt > 0 else 100.0
  g = lambda k, d=0.0: np.array([r.get(k, d) for r in rows], dtype=float)
  v, lat, en, tq, tqo = g('v'), g('lat'), g('en'), g('tq'), g('tqo')
  dla, ala, err, sat = g('dla'), g('ala'), g('err'), g('sat')
  prs, dtq, sft, sfp = g('prs'), g('dtq'), g('sft'), g('sfp')
  ang, rate, p, i, f = g('ang'), g('rate'), g('p'), g('i'), g('f')
  act = g('act')
  active = (lat > 0) & (act > 0) & (v > 5)
  out = dict(
    frames=len(rows), dur_s=float(t[-1] - t[0]), fs=round(fs, 1),
    moving_s=float((v > 1).sum() * dt), engaged_s=float((en > 0).sum() * dt),
    lat_active_s=float((lat > 0).sum() * dt), active_ctrl_s=float(active.sum() * dt),
    max_v=float(v.max()), mean_v_active=float(v[active].mean()) if active.any() else 0.0,
    steer_fault_temp_frames=int(sft.sum()), steer_fault_perm_frames=int(sfp.sum()),
    fault_temp_episodes=int(((sft[1:] > 0) & (sft[:-1] == 0)).sum()),
  )
  if active.sum() < 200:
    return out
  a = active
  e = dla[a] - ala[a]
  tqa = tq[a] * STEER_MAX
  dtqa = np.diff(tqa)
  # rate limit hits: |delta| >= rate-down limit 3 (per 100Hz frame torque units)
  out.update(
    track_rmse=float(np.sqrt(np.mean(e ** 2))), track_mae=float(np.mean(np.abs(e))),
    track_p95=float(np.percentile(np.abs(e), 95)), track_bias=float(np.mean(e)),
    track_bias_left=float(np.mean(e[dla[a] > 0.3])) if (dla[a] > 0.3).any() else 0.0,
    track_bias_right=float(np.mean(e[dla[a] < -0.3])) if (dla[a] < -0.3).any() else 0.0,
    # lag: cross-correlation of desired vs actual lat accel
    lag_s=float(xcorr_lag(dla[a], ala[a], fs)),
    sat_frac=float(sat[a].mean()), tq_abs_mean=float(np.abs(tqa).mean()),
    tq_abs_p95=float(np.percentile(np.abs(tqa), 95)), tq_at_max_frac=float((np.abs(tqa) >= STEER_MAX - 1).mean()),
    tq_rate_rms=float(np.sqrt(np.mean(dtqa ** 2)) * fs),  # torque units / s
    tq_rate_limited_frac=float((np.abs(dtqa) >= 2.0).mean()),
    tq_jerk_rms=float(np.sqrt(np.mean(np.diff(dtqa) ** 2)) * fs * fs),
    tq_sign_changes_per_min=float(((np.sign(tqa[1:]) * np.sign(tqa[:-1])) < 0).sum() / (a.sum() * dt) * 60),
    tq_osc_power_0p5_3hz=band_power(tqa, fs, 0.5, 3.0),
    tq_osc_power_3_10hz=band_power(tqa, fs, 3.0, 10.0),
    ala_osc_power_0p5_3hz=band_power(ala[a], fs, 0.5, 3.0),
    err_osc_power_0p5_3hz=band_power(e, fs, 0.5, 3.0),
    steer_rate_rms=float(np.sqrt(np.mean(rate[a] ** 2))),
    steer_rate_p95=float(np.percentile(np.abs(rate[a]), 95)),
    driver_pressed_frac=float(prs[a].mean()),
    driver_interventions=int(((prs[a][1:] > 0) & (prs[a][:-1] == 0)).sum()),
    driver_tq_abs_mean=float(np.abs(dtq[a]).mean()), driver_tq_p95=float(np.percentile(np.abs(dtq[a]), 95)),
    p_abs_mean=float(np.abs(p[a]).mean()), i_abs_mean=float(np.abs(i[a]).mean()), f_abs_mean=float(np.abs(f[a]).mean()),
    i_abs_p95=float(np.percentile(np.abs(i[a]), 95)),
    cmd_vs_output_mismatch_frac=float((np.abs(tq[a] - tqo[a]) > 0.02).mean()) if tqo.any() else None,
    by_speed=by_speed(v[a], e, tqa, sat[a], prs[a], dla[a], ala[a]),
  )
  return out

def xcorr_lag(d, m, fs, max_lag_s=1.0):
  d = d - d.mean(); m = m - m.mean()
  if np.std(d) < 1e-3 or np.std(m) < 1e-3: return 0.0
  ml = int(max_lag_s * fs); best, bl = -2, 0
  for l in range(0, ml):
    c = np.corrcoef(d[:len(d) - l], m[l:])[0, 1] if l else np.corrcoef(d, m)[0, 1]
    if c > best: best, bl = c, l
  return bl / fs

def by_speed(v, e, tqa, sat, prs, dla, ala):
  res = {}
  for name, lo, hi in (('5-13', 5, 13), ('13-22', 13, 22), ('22-30', 22, 30), ('30+', 30, 99)):
    m = (v >= lo) & (v < hi)
    if m.sum() < 100: continue
    res[name] = dict(s=int(m.sum()) / 100.0, rmse=float(np.sqrt(np.mean(e[m] ** 2))),
                     bias=float(e[m].mean()), sat=float(sat[m].mean()), prs=float(prs[m].mean()),
                     tq_abs=float(np.abs(tqa[m]).mean()),
                     gain_ratio=float(np.polyfit(dla[m], ala[m], 1)[0]) if np.std(dla[m]) > 0.05 else None)
  return res

def main():
  files = sorted(glob.glob(f'{SRC}/*.jsonl.gz'))
  routes = defaultdict(list)
  for fp in files:
    seg = os.path.basename(fp)[:-len('.jsonl.gz')]
    routes[seg.rsplit('--', 1)[0]].append(fp)
  report = {}
  for route, fps in sorted(routes.items()):
    rows_all, metas, events, alerts = [], [], [], []
    toff = 0.0
    for fp in fps:
      meta, rows = load(fp)
      metas.append(meta)
      seg_idx = int(fp.rsplit('--', 1)[1].split('.')[0])
      base = seg_idx * 60.0
      for r in rows: r['t'] = r['t'] + base
      rows_all += rows
      events += [[ev[0] + base] + ev[1:] for ev in meta.get('events', [])]
      alerts += [[al[0] + base] + al[1:] for al in meta.get('alerts', [])]
    m0 = metas[0]
    cp = m0.get('carParams') or {}
    tune = (cp.get('lateralTuning') or {}).get('torque') or {}
    live = [(mm.get('last') or {}).get('lateralTorqueParameters') for mm in metas]
    live = [l for l in live if l]
    vp = [(mm.get('last') or {}).get('vehicleParameters') for mm in metas]
    vp = [x for x in vp if x]
    ld = [(mm.get('last') or {}).get('lateralDelay') for mm in metas]
    ld = [x for x in ld if x]
    ev_counts = defaultdict(int)
    for ev in events:
      if ev[1] == 'onroadEvents':
        for n in ev[2]: ev_counts[n] += 1
    alert_counts = defaultdict(int)
    for al in alerts:
      if al[1]: alert_counts[al[1]] += 1
    st = seg_stats(rows_all) if rows_all else None
    report[route] = dict(
      segments=len(fps), init=m0.get('init'), params=m0.get('params_of_interest'),
      fingerprint=cp.get('carFingerprint'), carFw_count=len(cp.get('carFw') or []),
      carFw_ecus=sorted({fw.get('ecu') for fw in (cp.get('carFw') or [])}),
      fuzzy=((m0.get('iqCarParams') or {}).get('iqLateralNet') or {}).get('fuzzyFingerprint'),
      nn_model=(((m0.get('iqCarParams') or {}).get('iqLateralNet') or {}).get('model') or {}).get('name'),
      flags=cp.get('flags'), safetyParam=((cp.get('safetyConfigs') or [{}])[0]).get('safetyParam'),
      altExp=cp.get('alternativeExperience'), steerActuatorDelay=cp.get('steerActuatorDelay'),
      steerRatio_cp=cp.get('steerRatio'),
      tune_static=dict(laf=tune.get('latAccelFactor'), friction=tune.get('friction'), offset=tune.get('latAccelOffset')),
      live_torque_last=live[-1] if live else None,
      vehicle_params_last=vp[-1] if vp else None,
      lateral_delay_last=ld[-1] if ld else None,
      events=dict(sorted(ev_counts.items(), key=lambda x: -x[1])),
      alerts=dict(sorted(alert_counts.items(), key=lambda x: -x[1])[:25]),
      stats=st,
    )
    print(route, 'segs', len(fps), 'frames', len(rows_all), 'active_s', round((st or {}).get('active_ctrl_s', 0), 1) if st else None, flush=True)
  with open(OUT, 'w') as f:
    json.dump(report, f, indent=1)

if __name__ == '__main__':
  main()
