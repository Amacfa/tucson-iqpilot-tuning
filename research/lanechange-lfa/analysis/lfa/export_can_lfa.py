"""On-device bounded extractor: raw CAN frames for MDPS/LFA/LKAS/LFAHDA_CLUSTER (+sendcan LFA),
liveParameters roll/offsets, pandaStates, carState fault bits, controlsState enabled/active.
Output: /data/tucson-lfa-export/<seg>.jsonl.gz, one JSON per line: {"t":s,"k":kind,...}.
"""
import gzip, json, os, sys
sys.path.insert(0, '/data/openpilot')
import zstandard
from iqpilot.cereal import log

BASE = '/data/media/0/realdata'
OUT = '/data/tucson-lfa-export'
os.makedirs(OUT, exist_ok=True)
ADDRS = {234: 'MDPS', 298: 'LFA', 80: 'LKAS', 480: 'LFAHDA_CLUSTER', 676: 'CAM_0x2a4', 203: 'LFA_ALT', 272: 'LKAS_ALT'}
SUB = {234: 5, 676: 5}  # subsample factor for high-rate non-status msgs


def export(seg):
  path = f'{BASE}/{seg}/rlog.zst'
  out = f'{OUT}/{seg}.jsonl.gz'
  if os.path.exists(out) or not os.path.exists(path): return 'skip'
  origin = None
  counts = {}
  last_payload = {}
  with open(path, 'rb') as f:
    data = zstandard.ZstdDecompressor().stream_reader(f).read()
  with gzip.open(out, 'wt') as g:
    def emit(d):
      g.write(json.dumps(d, separators=(',', ':')) + '\n')
    for e in log.Event.read_multiple_bytes(data):
      w = e.which(); t = e.logMonoTime
      if origin is None and w in ('can', 'carState', 'sendcan'): origin = t
      s = round((t - origin) / 1e9, 3) if origin else -1.0
      if w in ('can', 'sendcan'):
        for c in (e.can if w == 'can' else e.sendcan):
          a = c.address
          if a not in ADDRS: continue
          key = (w, a, c.src)
          counts[key] = counts.get(key, 0) + 1
          dat = bytes(c.dat)
          if a in SUB and counts[key] % SUB[a]: continue
          # status-only messages: emit every frame (needed for exact timing), but mark unchanged payload
          emit({'t': s, 'k': w, 'a': a, 'b': c.src, 'd': dat.hex()})
      elif w == 'liveParameters':
        lp = e.liveParameters
        emit({'t': s, 'k': 'lp', 'roll': round(lp.roll, 5), 'ao': round(lp.angleOffsetDeg, 4),
              'aoa': round(lp.angleOffsetAverageDeg, 4), 'sr': round(lp.steerRatio, 3), 'sf': round(lp.stiffnessFactor, 3), 'valid': lp.valid})
      elif w == 'livePose':
        p = e.livePose
        emit({'t': s, 'k': 'pose', 'roll': round(p.orientationNED.x, 5), 'ay': round(p.accelerationDevice.y, 4), 'wz': round(p.angularVelocityDevice.z, 4)})
      elif w == 'selfdriveState':
        c = e.selfdriveState
        emit({'t': s, 'k': 'sds', 'en': c.enabled, 'act': c.active, 'st': str(c.state), 'alert': c.alertText1})
      elif w == 'pandaStates':
        for i, ps in enumerate(e.pandaStates):
          emit({'t': s, 'k': 'panda', 'i': i, 'ca': ps.controlsAllowed, 'sm': str(ps.safetyModel), 'sp': ps.safetyParam,
                'ign': ps.ignitionLine, 'rxinv': ps.safetyRxInvalid, 'txblk': ps.safetyTxBlocked, 'rxchk': ps.safetyRxChecksInvalid, 'ae': ps.alternativeExperience})
      elif w == 'carState':
        cs = e.carState
        emit({'t': s, 'k': 'cs', 'sft': cs.steerFaultTemporary, 'sfp': cs.steerFaultPermanent, 'prs': cs.steeringPressed,
              'v': round(cs.vEgo, 2), 'ang': round(cs.steeringAngleDeg, 2), 'tq': cs.steeringTorque, 'tqe': cs.steeringTorqueEps,
              'cc_en': cs.cruiseState.enabled, 'cc_av': cs.cruiseState.available, 'lb': cs.leftBlinker, 'rb': cs.rightBlinker})
      elif w == 'controlsState':
        c = e.controlsState
        emit({'t': s, 'k': 'ctl', 'lat': c.lateralControlState.torqueState.active, 'dc': round(c.desiredCurvature, 5)})
      elif w == 'carControl':
        c = e.carControl
        emit({'t': s, 'k': 'cc', 'la': c.latActive, 'tq': round(c.actuators.torque, 4)})
      elif w == 'carOutput':
        emit({'t': s, 'k': 'co', 'tq': round(e.carOutput.actuatorsOutput.torque, 4)})
      elif w == 'onroadEvents':
        emit({'t': s, 'k': 'ev', 'names': [str(x.name) for x in e.onroadEvents]})
    emit({'t': s, 'k': 'counts', 'c': {f'{k[0]}:{k[1]}:{k[2]}': v for k, v in counts.items()}})
  return 'ok'


if __name__ == '__main__':
  for seg in sys.argv[1:]:
    try:
      print(seg, export(seg), flush=True)
    except Exception as ex:
      print(seg, 'ERR', repr(ex)[:300], flush=True)
