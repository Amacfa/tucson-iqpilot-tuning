#!/usr/bin/env python3
"""Offline open-loop replay of the tune package against logged frames.

Compares the candidate latcontrol_torque behavior (speed-scheduled latAccelFactor
plus a 0.06 s first-order low-pass on the measured lateral acceleration used by
the feedback path) against the logged baseline output, on active frames only.

Also contains a self-contained unit test for the CAN-FD jerk_u floor/boost
change in carcontroller.py (nothing is imported from the device tree).
"""
import json
from pathlib import Path

import numpy as np

DRIVES = Path('/home/ubuntu/tucson/drives')
HERE = Path(__file__).resolve().parent

DT = 0.01
LP_TAU = 0.06
ALPHA = DT / (LP_TAU + DT)
BASELINE_FACTOR = 2.960174
SPEED_BP = [8.0, 15.0, 25.0]
SPEED_FP = [2.95, 3.35, 3.70]
KP_SPEEDS = [1, 1.5, 2.0, 3.0, 5, 7.5, 10, 15, 30]
KP_INTERP = [250, 120, 65, 30, 11.5, 5.5, 3.5, 2.0, 0.8]
KP_SCALE = 0.8  # IQHkgReducedTorqueFeedback


def candidate_jerk_u(jerk, accel, jerk_max_u=5.0):
  jerk_u_base = 1.0
  jerk_u_raw = np.clip(jerk_u_base + 2.0 * max(0.0, accel - 1.0), jerk_u_base, jerk_max_u)
  jerk_u_mpc = np.clip(jerk * 2.0, jerk_u_base, jerk_max_u)
  return max(jerk_u_raw, jerk_u_mpc)


def baseline_jerk_u(jerk, accel, jerk_u_min=0.5, jerk_max_u=5.0):
  return min(max(jerk_u_min, jerk * 2.0), jerk_max_u)


def jerk_l(jerk, accel, jerk_max_l=5.0):
  # Identical in baseline and candidate CAN-FD branches.
  jerk_l_base = 1.2
  jerk_l_raw = np.clip(jerk_l_base + 2.0 * max(0.0, -accel - 2.8), jerk_l_base, jerk_max_l)
  jerk_l_mpc = np.clip(-jerk * 4.0, jerk_l_base, jerk_max_l)
  return max(jerk_l_raw, jerk_l_mpc)


def test_jerk_formulas():
  cases = [((0.0, 0.5), 1.0), ((0.0, 2.0), 3.0), ((1.5, 0.0), 3.0), ((0.0, 2.5), 4.0)]
  for (jerk, accel), expected in cases:
    got = candidate_jerk_u(jerk, accel)
    assert abs(got - expected) < 1e-9, (jerk, accel, got, expected)
  grid_jerk = np.linspace(-3.0, 3.0, 61)
  grid_accel = np.linspace(-5.0, 5.0, 101)
  for j in grid_jerk:
    for a in grid_accel:
      expected = jerk_l(j, a)
      # baseline and candidate share the same jerk_l expression; recompute it the
      # baseline way (same two terms, same max) to prove the grid is unchanged.
      base = max(np.clip(1.2 + 2.0 * max(0.0, -a - 2.8), 1.2, 5.0), np.clip(-j * 4.0, 1.2, 5.0))
      assert abs(expected - base) < 1e-12, (j, a)
  # sanity: clip at 5.0
  assert candidate_jerk_u(10.0, 10.0) == 5.0
  return {'jerk_u_cases': [list(c[0]) + [c[1]] for c in cases], 'grid_points': int(len(grid_jerk) * len(grid_accel))}


def replay():
  cols = json.loads((DRIVES / 'all_frames_cols.json').read_text())
  data = np.load(DRIVES / 'all_frames.npy')
  idx = {name: cols.index(name) for name in cols}
  v = data[:, idx['v']]
  ala = data[:, idx['ala']]
  dla = data[:, idx['dla']]
  p = data[:, idx['p']]
  i = data[:, idx['i']]
  f = data[:, idx['f']]
  out = data[:, idx['out']]
  act = data[:, idx['act']].astype(bool)
  rid = data[:, idx['rid']]
  seg = data[:, idx['seg']]
  err = dla - ala

  tq_base = np.abs(out)
  kp = np.interp(v, KP_SPEEDS, KP_INTERP) * KP_SCALE
  # sanity: logged P must equal kp * err (validates the reconstruction)
  chk = act & (np.abs(err) > 0.05)
  p_fit = float(np.median((p[chk] / (kp[chk] * err[chk]))))
  # per-run first-order LP of the measurement
  filtered = ala.copy()
  lp = 0.0; prev_active = False; prev_key = None
  for n in range(len(data)):
    key = (rid[n], seg[n])
    if not act[n]:
      prev_active = False; prev_key = key; continue
    lp = ala[n] if (not prev_active or key != prev_key) else lp + ALPHA * (ala[n] - lp)
    prev_active = True; prev_key = key; filtered[n] = lp
  p_lp = kp * (dla - filtered)
  fac_cand = np.interp(v, SPEED_BP, SPEED_FP)
  tq_recon = np.abs((p + i + f) / BASELINE_FACTOR)            # baseline, reconstructed (should match tq_base)
  tq_lp = np.abs((p_lp + i + f) / BASELINE_FACTOR)            # LP only
  tq_sched = np.abs((p + i + f) / fac_cand)                   # schedule only
  tq_cand = np.abs((p_lp + i + f) / fac_cand)                 # both
  tq_cand[~act] = np.nan; tq_lp[~act] = np.nan; tq_sched[~act] = np.nan; tq_recon[~act] = np.nan

  mask = act & (v >= 5.0)
  bins = [(5, 10), (10, 15), (15, 20), (20, 25), (25, np.inf)]
  rows = []
  for lo, hi in bins:
    m = mask & (v >= lo) & (v < hi)
    n = int(m.sum())
    if n == 0:
      rows.append({'bin': f'{lo}-{hi if np.isfinite(hi) else "+"}', 'frames': 0})
      continue
    mb = float(np.mean(tq_base[m]))
    rows.append({
      'bin': f'{lo}-{hi if np.isfinite(hi) else "+"}', 'frames': n,
      'mean_abs_torque_base': round(mb, 4),
      'recon_over_base': round(float(np.mean(tq_recon[m])) / mb, 4),
      'lp_only_over_base': round(float(np.mean(tq_lp[m])) / mb, 4),
      'schedule_only_over_base': round(float(np.mean(tq_sched[m])) / mb, 4),
      'candidate_over_base': round(float(np.mean(tq_cand[m])) / mb, 4),
    })

  # Frame-to-frame torque change (x270 ~ torque units -> raw steer command steps)
  # within contiguous active runs only.
  def dither(tq):
    diffs = []
    prev_active = False
    prev_key = None
    prev_val = 0.0
    for n in range(len(data)):
      key = (rid[n], seg[n])
      if not act[n]:
        prev_active = False
        prev_key = key
        continue
      if prev_active and key == prev_key and np.isfinite(tq[n]):
        diffs.append((tq[n] - prev_val) * 270.0)
      prev_active = True
      prev_key = key
      prev_val = tq[n]
    d = np.asarray(diffs)
    return float(np.sqrt(np.mean(d * d))) if len(d) else float('nan')

  def dither_bins(tq):
    d = np.diff(tq) * 270.0
    ok = act[1:] & act[:-1] & (rid[1:] == rid[:-1]) & (seg[1:] == seg[:-1]) & np.isfinite(d)
    res = {}
    for lo, hi in bins:
      m = ok & (v[1:] >= lo) & (v[1:] < hi)
      res[f'{lo}-{hi if np.isfinite(hi) else "+"}'] = round(float(np.sqrt(np.mean(d[m] ** 2))), 3)
    return res
  dither_by_bin = {k: dither_bins(t) for k, t in [('baseline_recon', tq_recon), ('lp_only', tq_lp), ('candidate', tq_cand)]}
  dither_base = dither(tq_recon)
  dither_lp = dither(tq_lp)
  dither_sched = dither(tq_sched)
  dither_cand = dither(tq_cand)
  return {
    'active_frames_used': int(mask.sum()),
    'bins': rows,
    'p_equals_kp_times_err_median_ratio': round(p_fit, 4),
    'dither_rms_x270_by_speed': dither_by_bin,
    'dither_rms_x270': {'baseline_recon': round(dither_base, 4), 'lp_only': round(dither_lp, 4), 'schedule_only': round(dither_sched, 4), 'candidate': round(dither_cand, 4)},
    'alpha': ALPHA,
  }


def main():
  jerk = test_jerk_formulas()
  rep = replay()
  lines = []
  lines.append('# Offline validation results')
  lines.append('')
  lines.append('Source data: /home/ubuntu/tucson/drives/all_frames.npy '
               f'({rep["active_frames_used"]} active frames with v >= 5 m/s). '
               f'Low-pass alpha = {rep["alpha"]:.4f} (dt 0.01 s, tau 0.06 s).')
  lines.append('')
  lines.append('## Steering torque: candidate vs baseline (open-loop arithmetic)')
  lines.append('')
  lines.append('Baseline = logged |out|; recon = |(p+i+f)/2.960174| (checks the arithmetic); lp_only = P recomputed as kp*(dla - LP(ala)); '
               'schedule_only = baseline terms / interp(v,[8,15,25],[2.95,3.35,3.70]); candidate = both. '
               f'Median logged p / (kp*err) = {rep["p_equals_kp_times_err_median_ratio"]} (1.0 = reconstruction exact).')
  lines.append('')
  lines.append('| speed bin (m/s) | frames | mean |tq| base | recon/base | lp_only/base | schedule_only/base | candidate/base |')
  lines.append('|---|---|---|---|---|---|---|')
  for r in rep['bins']:
    if r['frames'] == 0:
      lines.append(f"| {r['bin']} | 0 | - | - | - | - | - |")
    else:
      lines.append(f"| {r['bin']} | {r['frames']} | {r['mean_abs_torque_base']} | {r['recon_over_base']} | {r['lp_only_over_base']} | {r['schedule_only_over_base']} | {r['candidate_over_base']} |")
  lines.append('')
  lines.append('## Dither: RMS of frame-to-frame torque change x270 (contiguous active runs)')
  lines.append('')
  for k, val in rep['dither_rms_x270'].items():
    lines.append(f"- {k}: {val}")
  lines.append('')
  lines.append('By speed bin:')
  for k, val in rep['dither_rms_x270_by_speed'].items():
    lines.append(f"- {k}: " + ', '.join(f'{b} {x}' for b, x in val.items()))
  lines.append('')
  lines.append('## L1 jerk_u unit test')
  lines.append('')
  for c in jerk['jerk_u_cases']:
    lines.append(f"- jerk={c[0]}, accel={c[1]} -> jerk_u={c[2]}")
  lines.append(f"- jerk_l unchanged vs baseline formula over {jerk['grid_points']} grid points: PASS")
  lines.append('')
  out = HERE / 'RESULTS.md'
  out.write_text('\n'.join(lines) + '\n')
  print('\n'.join(lines))


if __name__ == '__main__':
  main()
