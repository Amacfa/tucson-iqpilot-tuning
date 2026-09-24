"""On-device bounded exporter v2: v1 plus lead/longitudinal-plan per-frame fields."""
import gzip, json, os, sys, time
sys.path.insert(0, '/data/openpilot')
import zstandard
from iqpilot.cereal import log

BASE = '/data/media/0/realdata'
OUT = '/data/tucson-drive-export-v2'
os.makedirs(OUT, exist_ok=True)


def clean(x):
  if isinstance(x, dict): return {k: clean(v) for k, v in x.items()}
  if isinstance(x, list): return [clean(v) for v in x]
  if isinstance(x, bytes): return x.hex()
  if isinstance(x, float): return round(x, 5)
  return x


def export(seg):
  path = f'{BASE}/{seg}/rlog.zst'
  out = f'{OUT}/{seg}.jsonl.gz'
  if os.path.exists(out) or not os.path.exists(path): return 'skip'
  meta = {'segment': seg, 'services': {}, 'events': [], 'alerts': [], 'last': {}}
  frames = []; cs = None; cc = None; co = None; iq = None; origin = None
  rs = None; lp = None; mv = None; sd = None
  alert_prev = ('', '')
  dctx = zstandard.ZstdDecompressor()
  with open(path, 'rb') as f:
    data = dctx.stream_reader(f).read()
  if True:
    for e in log.Event.read_multiple_bytes(data):
      w = e.which(); meta['services'][w] = meta['services'].get(w, 0) + 1
      t = e.logMonoTime
      if origin is None:
        if w not in ('can', 'carState', 'sendcan'): origin_pending = True
        else: origin = t
      s = (t - origin) / 1e9 if origin else -1.0
      if w == 'initData':
        d = e.initData.to_dict(); meta['init'] = {k: d.get(k) for k in ('gitCommit', 'gitBranch', 'version', 'dirty', 'deviceType', 'osVersion')}
        meta['params_of_interest'] = {p['key']: p.get('value', b'').decode('utf-8', 'replace')[:80] for p in d.get('params', {}).get('entries', [])
          if p.get('key') in ('AutoEngage', 'AolEnabled', 'AolSteeringMode', 'IQHkgReducedTorqueFeedback', 'NeuralNetworkFeedForward', 'IQLateralAccelSlew',
                              'LiveTorqueParameters', 'IQLateralTune', 'IsMetric', 'AolMainCruiseAllowed', 'AolUnifiedEngagementMode',
                              'FingerprintOverride', 'IQCarModel', 'IsReleaseBranch',
                              'IQForceStops', 'CanfdStopRetry', 'IQCustomStopDistance',
                              'LongitudinalPersonality', 'ExperimentalMode')}
      elif w == 'carParams':
        d = e.carParams.to_dict(); meta['carParams'] = clean({k: d.get(k) for k in ('carFingerprint', 'carName', 'lateralTuning', 'steerActuatorDelay', 'steerLimitTimer', 'carFw',
          'flags', 'openpilotLongitudinalControl', 'mass', 'wheelbase', 'steerRatio', 'centerToFront', 'tireStiffnessFactor', 'safetyConfigs', 'alternativeExperience', 'steerControlType', 'minSteerSpeed')})
      elif w == 'iqCarParams':
        meta['iqCarParams'] = clean(e.iqCarParams.to_dict())
      elif w in ('lateralTorqueParameters', 'lateralDelay', 'vehicleParameters', 'liveCalibration', 'liveParameters', 'liveTorqueParameters'):
        d = clean(getattr(e, w).to_dict()); meta['last'][w] = d
        if w in ('lateralTorqueParameters', 'liveTorqueParameters') and meta['services'][w] == 1: meta['first_' + w] = d
      elif w in ('onroadEvents', 'iqOnroadEvents'):
        names = [str(x.name) for x in e.onroadEvents] if w == 'onroadEvents' else clean(e.iqOnroadEvents.to_dict())
        meta['events'].append([round(s, 3), w, names])
      elif w == 'selfdriveState':
        a = (e.selfdriveState.alertText1, e.selfdriveState.alertText2)
        if a != alert_prev:
          alert_prev = a; meta['alerts'].append([round(s, 3), a[0], a[1], str(e.selfdriveState.alertStatus), str(e.selfdriveState.state)])
        sd = dict(lper=str(e.selfdriveState.personality))
      elif w == 'carState':
        c = e.carState
        cs = dict(v=round(c.vEgo, 3), a=round(c.aEgo, 3), ang=round(c.steeringAngleDeg, 3), rate=round(c.steeringRateDeg, 2), dtq=round(c.steeringTorque, 1),
                  dtqe=round(c.steeringTorqueEps, 2), prs=int(c.steeringPressed), sft=int(c.steerFaultTemporary), sfp=int(c.steerFaultPermanent),
                  avail=int(c.cruiseState.available), cen=int(c.cruiseState.enabled), ss=int(c.standstill), brk=int(c.brakePressed), gas=int(c.gasPressed),
                  yaw=round(c.yawRate, 4), lb=int(c.leftBlinker), rb=int(c.rightBlinker))
      elif w == 'carControl':
        c = e.carControl
        cc = dict(lat=int(c.latActive), en=int(c.enabled), lon=int(c.longActive), tq=round(c.actuators.torque, 4), curv=round(c.actuators.curvature, 5),
                  acc=round(c.actuators.accel, 3), ldw=int(c.hudControl.leftLaneDepart or c.hudControl.rightLaneDepart),
                  lcs=str(c.actuators.longControlState), cc_at=round(c.actuators.aTarget, 3))
      elif w == 'radarState':
        l = e.radarState.leadOne
        rs = dict(l1s=int(l.status), ldr=round(l.dRel, 2), lvr=round(l.vRel, 3), lvl=round(l.vLead, 3),
                  lak=round(l.aLeadK, 3), lmp=round(l.modelProb, 3))
      elif w == 'longitudinalPlan':
        p = e.longitudinalPlan
        lp = dict(lp_at=round(p.aTarget, 3), sstop=int(p.shouldStop), hlead=int(p.hasLead), lps=str(p.longitudinalPlanSource))
      elif w == 'modelV2':
        lv = e.modelV2.leadsV3
        mv = dict(mprob=round(lv[0].prob, 3), mx=round(lv[0].x[0], 1)) if len(lv) else dict(mprob=0.0, mx=0.0)
      elif w == 'carOutput':
        co = round(e.carOutput.actuatorsOutput.torque, 4)
      elif w == 'iqState':
        iq = clean(e.iqState.to_dict().get('aol', {}))
      elif w == 'controlsState':
        c = e.controlsState; lcs = c.lateralControlState
        row = dict(t=round(s, 3), curv=round(c.curvature, 5))
        if lcs.which() == 'torqueState':
          ts = lcs.torqueState
          row.update(act=int(ts.active), err=round(ts.error, 4), p=round(ts.p, 4), i=round(ts.i, 4), d=round(ts.d, 4), f=round(ts.f, 4), out=round(ts.output, 4),
                     sat=int(ts.saturated), ala=round(ts.actualLateralAccel, 4), dla=round(ts.desiredLateralAccel, 4))
        else:
          row['lcs'] = lcs.which()
        if cs: row.update(cs)
        if cc: row.update(cc)
        if co is not None: row['tqo'] = co
        if iq: row['aol'] = iq.get('state')
        if rs: row.update(rs)
        if lp: row.update(lp)
        if mv: row.update(mv)
        if sd: row.update(sd)
        frames.append(row)
  meta['frames'] = len(frames); meta['duration_s'] = frames[-1]['t'] if frames else 0
  with gzip.open(out, 'wt') as g:
    g.write(json.dumps({'meta': meta}) + '\n')
    for r in frames: g.write(json.dumps(r) + '\n')
  return 'ok %d frames' % len(frames)


if __name__ == '__main__':
  segs = sorted(d for d in os.listdir(BASE) if '--' in d and os.path.isdir(f'{BASE}/{d}'))
  if len(sys.argv) > 1: segs = [s for s in segs if s.startswith(tuple(sys.argv[1:]))]
  for seg in segs:
    t0 = time.time()
    try: r = export(seg)
    except Exception as ex:
      import traceback; traceback.print_exc(); r = 'ERR %r' % ex
    print(seg, r, '%.1fs' % (time.time() - t0), flush=True)
