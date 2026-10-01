"""On-device: engage-failure evidence. Usage: extract_engage.py <seg>... ; prints one JSON line per seg."""
import json, os, sys
sys.path.insert(0, '/data/openpilot')
import zstandard
from iqpilot.cereal import log
BASE = '/data/media/0/realdata'
for seg in sys.argv[1:]:
  path = f'{BASE}/{seg}/rlog.zst'
  if not os.path.exists(path): print(json.dumps({'seg': seg, 'err': 'missing'})); continue
  r = {'seg': seg, 'panda': [], 'cs': [], 'btn': [], 'sd': [], 'alerts': [], 'ev': [], 'can1a0': {}, 'send1a0': 0, 'cp': None, 'n': {}}
  origin = None; pp = None; csp = None; sdp = None; ap = None
  data = zstandard.ZstdDecompressor().stream_reader(open(path, 'rb')).read()
  for e in log.Event.read_multiple_bytes(data):
    w = e.which(); r['n'][w] = r['n'].get(w, 0) + 1
    t = e.logMonoTime
    if origin is None and w in ('can', 'carState', 'sendcan'): origin = t
    s = round((t - origin) / 1e9, 2) if origin else -1.0
    if w == 'pandaStates':
      for i, p in enumerate(e.pandaStates):
        d = p.to_dict(); k = tuple([i] + [str(d.get(f)) for f in ('safetyModel', 'safetyParam', 'controlsAllowed', 'alternativeExperience', 'ignitionLine', 'ignitionCan', 'faultStatus', 'harnessStatus', 'safetyRxChecksInvalid', 'safetyRxInvalid', 'faults')])
        if k != pp: r['panda'].append([s] + list(k)); pp = k
    elif w == 'carParams':
      d = e.carParams.to_dict(); r['cp'] = {k: d.get(k) for k in ('carFingerprint', 'safetyConfigs', 'alternativeExperience', 'openpilotLongitudinalControl', 'flags')}
    elif w == 'carState':
      c = e.carState
      k = (int(c.cruiseState.available), int(c.cruiseState.enabled), int(c.canValid), int(c.canTimeout), str(c.gearShifter), int(c.brakePressed))
      if k != csp: r['cs'].append([s, round(c.vEgo, 1), round(c.cruiseState.speed, 1)] + list(k)); csp = k
      for b in c.buttonEvents: r['btn'].append([s, str(b.type), int(b.pressed)])
    elif w == 'selfdriveState':
      d = e.selfdriveState
      k = (int(d.enabled), int(d.active), str(d.state))
      if k != sdp: r['sd'].append([s] + list(k)); sdp = k
      a = (str(d.alertText1), str(d.alertText2))
      if a != ap and a[0]: r['alerts'].append([s, a[0], a[1][:60]]); ap = a
    elif w == 'onroadEvents':
      names = sorted(str(x.name) for x in e.onroadEvents)
      if not r['ev'] or r['ev'][-1][1] != names: r['ev'].append([s, names])
    elif w == 'can':
      for m in e.can:
        if m.address == 0x1a0:
          b = int(m.src); kk = f'{int(s//10)*10}'; r['can1a0'].setdefault(kk, {}); r['can1a0'][kk][b] = r['can1a0'][kk].get(b, 0) + 1
    elif w == 'sendcan':
      for m in e.sendcan:
        if m.address == 0x1a0: r['send1a0'] += 1
  r['ev'] = r['ev'][:80]; r['alerts'] = r['alerts'][:60]; r['cs'] = r['cs'][:80]
  print(json.dumps(r, default=str))
