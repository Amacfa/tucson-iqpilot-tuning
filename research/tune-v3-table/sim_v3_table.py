#!/usr/bin/env python3
"""Run sim_curve_exit + sim_handback with the tune-v3 latAccelFactor table vs tune-v2.
No changes to either script: curve_exit takes factor_table via Controller kwarg;
handback reads the module-global LAF_TABLE which we monkeypatch per run."""
import json, sys
import numpy as np

V2_TABLE = ([8.0, 15.0, 25.0], [2.95, 3.35, 3.70])
V3_TABLE = ([8.0, 12.0, 15.0, 25.0], [2.95, 3.20, 3.80, 3.90])

import sim_curve_exit as ce
import sim_handback as hb

# ---- curve exit (replicates main()'s exit loop, v2 vs v3 only) ----
for npz in ('v2_frames.npz', 'drive1_frames.npz'):
    d = np.load(npz, allow_pickle=True)
    v, la, tq = d["vEgo"], d["ala"], -d["tqo"]
    des, act = d["dla"], d["act"].astype(bool)
    pressed = d["prs"].astype(bool); seg = d["seg"]
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
            if np.all(np.diff(d["t"][e - 100:e + W]) < 0.03) and not pressed[e:e + W].any() and act[e:e + W].all():
                exits.append(e)
    exits = [e for i, e in enumerate(exits) if i == 0 or e - exits[i - 1] > W]
    res = {}
    for name, kw in (('v2', dict(factor_table=V2_TABLE)), ('v3', dict(factor_table=V3_TABLE))):
        ftq, fla, rms = [], [], []
        for e in exits:
            sl = slice(e - 100, e + W)
            c = ce.Controller(**kw)
            la_s, tq_s = ce.simulate(v[sl], des[sl], plant, c, la[e - 100], tq[e - 100])
            ftq.append(ce.band_fraction(tq_s[100:])); fla.append(ce.band_fraction(la_s[100:]))
            rms.append(float(np.std(np.diff(tq_s[100:])) * ce.STEER_MAX))
        res[name] = {"band_frac_torque": round(float(np.mean(ftq)), 3),
                     "band_frac_lataccel": round(float(np.mean(fla)), 3),
                     "dither_x270": round(float(np.mean(rms)), 2)}
    ftq = [ce.band_fraction(tq[e:e + W]) for e in exits]
    res['logged'] = round(float(np.mean(ftq)), 3)
    print('CURVE_EXIT', npz, 'exits', len(exits), json.dumps(res))

# ---- handback ----
plant_p = json.load(open('/home/ubuntu/tucson/analysis/wobble/plant_fit.json'))
for name, tbl in (('v2', V2_TABLE), ('v3', V3_TABLE)):
    hb.LAF_TABLE = tbl
    o = hb.run({}, plant_p)
    print('HANDBACK', name, ' '.join('%s=%.3f' % kv for kv in hb.metrics(o).items()))
