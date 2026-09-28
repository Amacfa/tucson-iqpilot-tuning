"""Scan all exported segments for native warning-like states while moving:
 - MDPS LKA_FAULT / LFA2_FAULT
 - camera LFA (298, bus 2) LKA_WARNING, FCA_SYSWARN, LKA_MODE changes, VALUE63
 - cluster (480, bus 2) HDA_InfoPUDis popups, HDA_LFA_WrnSnd
 - panda safetyTxBlocked / safetyRxInvalid deltas
Prints per-event context: speed, IQ state (enabled/active/alert), STEER_REQ on sendcan, MDPS LKA_ACTIVE."""
import glob, os, json
import numpy as np
from decode import EXPORT, decode, load

WATCH = {
  (234, 0): ['LKA_FAULT', 'LFA2_FAULT', 'LKA_ACTIVE'],
  (298, 2): ['LKA_MODE', 'LKA_WARNING', 'FCA_SYSWARN', 'VALUE63', 'LKA_ICON', 'STEER_REQ'],
  (480, 2): ['HDA_InfoPUDis', 'HDA_LFA_WrnSnd', 'HDA_LFA_SymSta', 'LFA_OptUsmSta'],
}

events = []
segs = sorted(os.path.basename(p)[:-9] for p in glob.glob(os.path.join(EXPORT, '*.jsonl.gz')))
summary = {}
for seg in segs:
  st = {}
  speed = 0.0; sds = {}; steer_req = None; mdps_act = None; panda = {}
  moving_warn = 0
  popup_open = {}
  for r in load(seg):
    k = r['k']
    if k == 'cs':
      speed = r.get('v', speed)
    elif k == 'sds':
      sds = r
    elif k == 'panda':
      prev = panda.get(r['i'])
      if prev is not None and (r['txblk'] != prev['txblk'] or r['rxinv'] != prev['rxinv']):
        events.append((seg, r['t'], speed, 'PANDA', dict(dtx=r['txblk'] - prev['txblk'], drx=r['rxinv'] - prev['rxinv']), sds.get('st'), steer_req, mdps_act))
      panda[r['i']] = r
    elif k == 'sendcan' and r['a'] == 298:
      d = decode(298, r['d'])
      if d:
        steer_req = d['STEER_REQ']
    elif k == 'can' and (r['a'], r['b']) in WATCH:
      d = decode(r['a'], r['d'])
      if not d:
        continue
      key = (r['a'], r['b'])
      if key == (234, 0):
        mdps_act = d['LKA_ACTIVE']
      cur = {s: d[s] for s in WATCH[key]}
      prev = st.get(key)
      if prev is None:
        st[key] = cur; continue
      ch = {s: cur[s] for s in cur if cur[s] != prev[s]}
      if ch:
        st[key] = cur
        interesting = False
        if key == (234, 0) and ('LKA_FAULT' in ch or 'LFA2_FAULT' in ch):
          interesting = True
        if key == (298, 2) and any(s in ch for s in ('LKA_WARNING', 'FCA_SYSWARN', 'VALUE63', 'LKA_MODE')):
          interesting = True
        if key == (480, 2) and any(s in ch for s in ('HDA_InfoPUDis', 'HDA_LFA_WrnSnd')):
          interesting = True
        if interesting:
          events.append((seg, r['t'], speed, key, ch, sds.get('st'), steer_req, mdps_act))
          if speed > 3:
            moving_warn += 1
  summary[seg] = moving_warn

print('segments:', len(segs))
print('segments with moving warning-like changes:', {s: n for s, n in summary.items() if n})
for e in events:
  seg, t, v, key, ch, sst, sr, ma = e
  flag = 'MOVING' if v > 3 else 'stopped'
  print(f'{seg} {t:7.3f} v={v:5.1f} {flag:7s} {key} {ch} iq={sst} steer_req={sr} mdps_act={ma}')
