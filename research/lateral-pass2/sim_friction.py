#!/usr/bin/env python3
"""Friction sensitivity + handback-fix-on-v3 sims.
monkeypatch hb.FRICTION / hb.LAF_TABLE; curve_exit Controller(friction=, factor_table=).
No changes to the sim scripts."""
import json
import numpy as np
import sim_curve_exit as ce
import sim_handback as hb

V2_TABLE = ([8.0, 15.0, 25.0], [2.95, 3.35, 3.70])
V3_TABLE = ([8.0, 12.0, 15.0, 25.0], [2.95, 3.20, 3.80, 3.90])
plant_p = json.load(open('/home/ubuntu/tucson/analysis/wobble/plant_fit.json'))

# ---- handback: v3 table x friction {0.12, 0.09, 0.06} ----
for fr in (0.12, 0.09, 0.06):
    hb.LAF_TABLE = V3_TABLE; hb.FRICTION = fr
    o = hb.run({}, plant_p)
    print('HANDBACK v3 fric=%.2f' % fr, ' '.join('%s=%.3f' % kv for kv in hb.metrics(o).items()))
# v2 table for reference
hb.LAF_TABLE = V2_TABLE; hb.FRICTION = 0.12
o = hb.run({}, plant_p)
print('HANDBACK v2 fric=0.12', ' '.join('%s=%.3f' % kv for kv in hb.metrics(o).items()))

# ---- handback fix on v3: p x0.6 >15 m/s + 0.3 s friction smoothing (cfg C) ----
hb.LAF_TABLE = V3_TABLE; hb.FRICTION = 0.12
for name, cfg in (('v3 base', {}),
                  ('v3 + P x0.6 >15m/s', dict(p_scale=lambda v: np.interp(v, [12, 15], [1.0, 0.6]))),
                  ('v3 + 0.3s friction lp', dict(friction_tau=0.3)),
                  ('v3 + fix C (P x0.6 + fric lp)', dict(p_scale=lambda v: np.interp(v, [12, 15], [1.0, 0.6]), friction_tau=0.3))):
    o = hb.run(cfg, plant_p)
    print('HANDBACK', name, ' '.join('%s=%.3f' % kv for kv in hb.metrics(o).items()))

# ---- curve-exit: v3 table x friction ----
d = np.load('v2_frames.npz', allow_pickle=True)
v, la, tq = d["vEgo"], d["ala"], -d["tqo"]
des, act = d["dla"], d["act"].astype(bool)
pressed = d["prs"].astype(bool); seg = d["seg"]; tt = d["t"]
W = 300
ok = act & ~pressed & (v > 3)
plant = ce.fit_plant(v, tq, la, ok)
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
        if np.all(np.diff(tt[e - 100:e + W]) < 0.03) and not pressed[e:e + W].any() and act[e:e + W].all():
            exits.append(e)
exits = [e for i, e in enumerate(exits) if i == 0 or e - exits[i - 1] > W]
for fr in (0.12, 0.09, 0.06):
    for tbl_name, tbl in (('v2', V2_TABLE), ('v3', V3_TABLE)):
        ftq, fla, rms = [], [], []
        for e in exits:
            sl = slice(e - 100, e + W)
            c = ce.Controller(factor_table=tbl, friction=fr)
            la_s, tq_s = ce.simulate(v[sl], des[sl], plant, c, la[e - 100], tq[e - 100])
            ftq.append(ce.band_fraction(tq_s[100:])); fla.append(ce.band_fraction(la_s[100:]))
            rms.append(float(np.std(np.diff(tq_s[100:])) * ce.STEER_MAX))
        print('CURVE_EXIT', tbl_name, 'fric=%.2f' % fr,
              'band_tq=%.3f band_la=%.3f dither=%.2f' % (np.mean(ftq), np.mean(fla), np.mean(rms)))
