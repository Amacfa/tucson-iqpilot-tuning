#!/usr/bin/env python3
# Mechanism tests for v3+H1+D1 anomalies: curve-exit tr 1.44, saturation 1.12%.
# Open-loop replay of the INSTALLED latcontrol_torque logic on route 0000002d:
# recorded dla is the post-lookahead setpoint (delay=0.15), so reconstruct the
# buffer input as dla shifted +0.15 s, then replay delay={0.15,0.30} x LP={on,off}.
# Validation: delay=0.15, LP on must reproduce recorded -tqo.
# Also: saturation census (sat flag / |tqo|>=1) + per-curve tr_exit list.
import gzip, json, glob, os
import numpy as np

EXP = os.environ.get('TUCSON_V3B_DIR', '/home/ubuntu/tucson/drives/export-v3b')
DT = 0.01
INTERP_SPEEDS = [1, 1.5, 2.0, 3.0, 5, 7.5, 10, 15, 30]
KP_INTERP = [250, 120, 65, 30, 11.5, 5.5, 3.5, 2.0, 0.8]
KI = 0.15
FRICTION_THRESHOLD = 0.3
JERK_LOOKAHEAD_SECONDS = 0.19
JERK_GAIN = 0.3
LP_TAU = 1 / (2 * np.pi * 1.2)
LAF_TABLE = ([8.0, 12.0, 15.0, 25.0], [2.95, 3.20, 3.80, 3.90])
LAF_V2 = ([8.0, 15.0, 25.0], [2.95, 3.35, 3.70])
FRICTION = 0.12
STEER_MAX_NORM = 1.0  # latcontrol steer_max is normalized 1.0
JERK_SPEED_BP = [0.0, 8.0, 20.0, 35.0]; JERK_MAX_BP = [5.0, 4.0, 2.5, 2.0]
A_LAT_MAX = 3.0; MIN_LIMIT_SPEED = 5.0; BYPASS = 2.0
FRIC_SCALE = 0.7  # IQHkgReducedTorqueFeedback=1
KP_REDUCED = 0.8

def load_seg(path):
    with gzip.open(path, 'rt') as g:
        meta = json.loads(g.readline())['meta']
        rows = [r for r in (json.loads(l) for l in g) if 'v' in r]
    return meta, rows

def replay(v, meas, future, active, prs, lat_delay, fric_lp_on, laf_table=LAF_TABLE):
    """future = un-delayed desired lat accel (slew-limited input). Returns out_tq, p, f_la, setpoint."""
    n = len(v)
    buflen = int(1.0 / DT)
    buf = [0.0] * buflen
    lookahead_frames = int(JERK_LOOKAHEAD_SECONDS / DT)
    delay_frames = int(np.clip(lat_delay / DT + 1, 1, buflen))
    i_term = 0.0
    fric_err = 0.0
    jf = 0.0
    a_lim = 0.0
    out = np.zeros(n); PP = np.zeros(n); FF = np.zeros(n); SP = np.zeros(n)
    for k in range(n):
        vk = v[k]
        # slew limiter on the reconstructed input (idempotent if already limited)
        a_des = future[k]
        if vk < MIN_LIMIT_SPEED:
            a_lim = float(np.clip(a_des, -A_LAT_MAX, A_LAT_MAX)); lim = a_des
        elif abs(a_des - a_lim) > BYPASS:
            a_lim = float(np.clip(a_des, -A_LAT_MAX, A_LAT_MAX)); lim = a_des
        else:
            da = float(np.interp(vk, JERK_SPEED_BP, JERK_MAX_BP)) * DT
            a_lim += float(np.clip(a_des - a_lim, -da, da)); a_lim = float(np.clip(a_lim, -A_LAT_MAX, A_LAT_MAX))
            lim = a_lim
        buf.append(lim); buf.pop(0)
        setpoint = buf[-delay_frames]
        error = setpoint - meas[k]
        li = int(np.clip(-delay_frames + lookahead_frames, -buflen + 1, -2))
        raw_jerk = (buf[li + 1] - buf[li - 1]) / (2 * DT)
        jf += (raw_jerk - jf) * DT / LP_TAU
        laf = float(np.interp(vk, *laf_table))
        if fric_lp_on:
            fric_err += (error - fric_err) * DT / 0.3
            fe = fric_err
        else:
            fe = error
        deadzone = 0.0  # steeringAngleDeadzoneDeg ~0; effect <1%
        e_dz = 0.0 if abs(fe) < deadzone else fe
        fric = FRIC_SCALE * float(np.interp(e_dz + JERK_GAIN * jf, [-FRICTION_THRESHOLD, FRICTION_THRESHOLD],
                                            [-FRICTION * laf, FRICTION * laf]))
        ff = lim - 0.0 + fric  # latAccelOffset ~0
        if not active[k]:
            out[k] = 0.0; SP[k] = setpoint; continue
        pos_lim = STEER_MAX_NORM * laf
        kp = float(np.interp(vk, INTERP_SPEEDS, [x * KP_REDUCED for x in KP_INTERP])) \
             * float(np.interp(vk, [13.0, 17.0], [1.0, 0.6]))
        p = kp * error
        freeze = bool(prs[k]) or vk < 5
        if not freeze:
            i_new = i_term + KI * DT * error
            test = p + i_new + ff
            ub = i_term if test > pos_lim else pos_lim
            lb = i_term if test < -pos_lim else -pos_lim
            i_term = float(np.clip(i_new, lb, ub))
        out_la = float(np.clip(p + i_term + ff, -pos_lim, pos_lim))
        tq = out_la / laf
        out[k] = tq; PP[k] = p; FF[k] = ff; SP[k] = setpoint
    return out, PP, FF, SP

print('=== replay validation + counterfactuals (route 2d, lat-active unpressed frames) ===')
allres = {k: [] for k in ('015_lp', '030_lp', '015_nolp', 'rec')}
exit_rows = []
sat_events = []
curves_out = []
for path in sorted(glob.glob(f'{EXP}/0000002d*.jsonl.gz')):
    seg = os.path.basename(path)[:-9]
    meta, rows = load_seg(path)
    T = np.array([r['t'] for r in rows]); V = np.array([r.get('v') or 0 for r in rows])
    ALA = np.array([r.get('ala') or 0 for r in rows]); DLA = np.array([r.get('dla') or 0 for r in rows])
    TQ = np.array([-(r.get('tqo') or 0) for r in rows])
    ACT = np.array([bool(r.get('lat')) for r in rows]); PRS = np.array([bool(r.get('prs')) for r in rows])
    SAT = np.array([bool(r.get('sat')) for r in rows])
    n = len(rows)
    if n < 50: continue
    # reconstruct un-delayed input: dla[k] = buf[-16]; input at frame k+15
    fut = np.concatenate([DLA[int(0.15 / DT):], DLA[-int(0.15 / DT):]])  # shift back 0.15s
    o15, p15, f15, sp15 = replay(V, ALA, fut, ACT, PRS, 0.15, True)
    o30, p30, f30, sp30 = replay(V, ALA, fut, ACT, PRS, 0.30, True)
    o15n, p15n, f15n, _ = replay(V, ALA, fut, ACT, PRS, 0.15, False)
    okm = ACT & ~PRS & (V >= 5)
    for name, o in (('015_lp', o15), ('030_lp', o30), ('015_nolp', o15n), ('rec', TQ)):
        allres[name].append((okm, o))
    # validation error
    e = o15[okm] - TQ[okm]
    print(seg, 'replay015 vs rec: rmse %.3f corr %.3f n=%d' % (float(np.sqrt(np.mean(e**2))),
          float(np.corrcoef(o15[okm], TQ[okm])[0, 1]), int(okm.sum())))
    # exit windows: dla decays >0.8 -> <0.3, next 4s
    i = 0
    while i < n - 400:
        if abs(DLA[i]) > 0.8 and ACT[i] and not PRS[i]:
            j = i
            while j < n and abs(DLA[j]) > 0.3: j += 1
            if j - i > 100 and j < n - 200:
                s = slice(j, min(j + 400, n))
                m = okm[s]
                if m.sum() > 100:
                    exit_rows.append(dict(seg=seg, t=round(float(T[j]), 1), v=round(float(V[j]), 1),
                        rec_exit_mean=round(float(np.mean(TQ[s][m])), 3),
                        d015=round(float(np.mean(o15[s][m] - TQ[s][m])), 3),
                        d030=round(float(np.mean(o30[s][m] - TQ[s][m])), 3),
                        ff_d=round(float(np.mean((f15[s] - f30[s]) / np.interp(V[s], *LAF_V2))), 3),
                        lp_d=round(float(np.mean((o15n[s][m] - o15[s][m]))), 3)))
                i = j
        i += 1
    # saturation census
    k = 0
    while k < n:
        if SAT[k] or abs(TQ[k]) >= 0.995:
            kk = k
            while kk < n and (SAT[kk] or abs(TQ[kk]) >= 0.995): kk += 1
            pre = slice(max(0, k - 300), k)
            pre_dla = np.max(np.abs(DLA[pre])) if pre.stop > pre.start else 0.0
            ctx = 'curve-exit' if pre_dla > 0.8 and np.max(np.abs(DLA[k:kk])) < 0.6 else \
                  ('override' if np.any(PRS[pre]) or np.any(PRS[k:kk]) else ('curve' if np.max(np.abs(DLA[k:kk])) > 0.8 else 'straight'))
            sat_events.append(dict(seg=seg, t=round(float(T[k]), 1), dur=round((kk - k) * DT, 2),
                                   v=round(float(np.median(V[k:kk])), 1), ctx=ctx,
                                   dla=round(float(np.max(np.abs(DLA[k:kk]))), 2),
                                   p=round(float(np.mean(np.abs([r.get('p', 0) for r in rows[k:kk]]))), 2),
                                   f=round(float(np.mean(np.abs([r.get('f', 0) for r in rows[k:kk]]))), 2)))
            k = kk
        k += 1
    # per-curve tr_exit
    m2 = (np.abs(DLA) > 0.8) & ACT & ~PRS
    i = 0
    while i < n:
        if not m2[i]: i += 1; continue
        j = i
        while j < n and m2[j]: j += 1
        if (j - i) * DT >= 2.0:
            nn = int(0.6 / DT)
            ss = slice(j - nn, j)
            dd = np.mean(np.abs(DLA[ss]))
            curves_out.append((seg, round(float(T[i]), 1), round(float(np.median(V[i:j])), 1),
                               round(float(np.mean(ALA[ss] * np.sign(DLA[ss])) / dd), 2) if dd > 0.3 else None))
        i = j

print('\n=== exit windows: replay-vs-recorded mean torque diff ===')
for r in exit_rows: print(r)
print('\n=== saturation events (sat flag or |tqo|>=0.995) ===')
for s_ in sat_events: print(s_)
print('\n=== per-curve tr_exit (seg, t, v, tr_exit) ===')
for c in curves_out: print(c)
