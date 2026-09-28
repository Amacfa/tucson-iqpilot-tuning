"""Per-segment change log of LFA/MDPS/cluster status signals + app state; popup (HDA_InfoPUDis) event list."""
import collections, json, sys
from decode import decode, load, segs

STATUS = {
  234: ['LKA_ACTIVE', 'LKA_FAULT', 'LFA2_ACTIVE', 'LFA2_FAULT', 'NEW_SIGNAL_1', 'NEW_SIGNAL_2', 'NEW_SIGNAL_3', 'NEW_SIGNAL_4', 'NEW_SIGNAL_5', 'NEW_SIGNAL_6'],
  298: ['LKA_MODE', 'LKA_ACTIVE', 'LKA_WARNING', 'LKA_ICON', 'FCA_SYSWARN', 'STEER_REQ', 'LFA_BUTTON', 'VALUE63', 'VALUE64', 'NEW_SIGNAL_1', 'LKAS_ANGLE_ACTIVE', 'HAS_LANE_SAFETY', 'LKAS_ANGLE_MAX_TORQUE', 'DampingGain'],
  80: ['LKA_MODE', 'LKA_ACTIVE', 'LKA_WARNING', 'LKA_ICON', 'STEER_REQ', 'VALUE63', 'VALUE64', 'DampingGain'],
  480: ['HDA_OptUsmSta', 'LFA_OptUsmSta', 'HDA_CntrlModSta', 'HDA_InfoPUDis', 'HDA_LFA_SymSta', 'HDA_LFA_WrnSnd', 'HDA_InfoPUDis1', 'HDA_TDMRMDclReq'],
}
APP = {'cs': ['sft', 'sfp', 'prs', 'cc_en', 'cc_av', 'lb', 'rb'], 'ctl': ['lat'], 'cc': ['la'], 'sds': ['en', 'act', 'st', 'alert'],
       'panda': ['ca', 'sm', 'sp', 'rxinv', 'txblk', 'rxchk', 'ae'], 'lp': ['valid']}


def analyze(seg):
  last = {}
  changes = []          # (t, key, changed_fields)
  popups = []           # (t_start, t_end, value, source_bus)
  open_pu = {}
  ev = []
  speed = 0.0
  for r in load(seg):
    k = r['k']
    if k == 'counts':
      continue
    if k in ('can', 'sendcan'):
      a = r['a']
      if a not in STATUS:
        continue
      d = decode(a, r['d'])
      if d is None:
        continue
      key = (k, a, r['b'])
      st = {s: d[s] for s in STATUS[a] if s in d}
      if a == 234:
        st.pop('NEW_SIGNAL_3', None)  # counter-like
    elif k in APP:
      key = (k, r.get('i', 0))
      st = {s: r.get(s) for s in APP[k]}
      if k == 'cs':
        speed = r['v']
    elif k == 'ev':
      ev.append((r['t'], r['names']))
      continue
    else:
      continue
    prev = last.get(key)
    if prev != st:
      diff = {s: v for s, v in st.items() if prev is None or prev.get(s) != v}
      changes.append((r['t'], key, diff, speed))
      last[key] = st
      if key[0] == 'can' and key[1] == 480:
        pu = st.get('HDA_InfoPUDis', 0)
        b = key[2]
        if pu and b not in open_pu:
          open_pu[b] = (r['t'], pu)
        elif not pu and b in open_pu:
          t0, val = open_pu.pop(b)
          popups.append((t0, r['t'], val, b, speed))
  return changes, popups, ev


if __name__ == '__main__':
  sel = sys.argv[1:] or segs()
  allpop = []
  for seg in sel:
    ch, pu, ev = analyze(seg)
    for p in pu:
      allpop.append((seg,) + p)
    if len(sys.argv) > 1:
      for t, key, diff, v in ch:
        print(f'{t:8.3f} v={v:5.1f} {key} {diff}')
      for t, names in ev:
        print(f'{t:8.3f} EV {names}')
  print('\nPOPUPS (HDA_InfoPUDis != 0 from camera bus):')
  for p in allpop:
    print('  ', p)
  json.dump(allpop, open('/home/ubuntu/tucson/analysis/lfa/popups.json', 'w'), indent=1)
