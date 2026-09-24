"""Isolated route23 runtime replay: PAYLOAD in, RESULT out. Run inside the parked guard.

Actual installed CANParser/interfaces/schema, actual original and candidate CarState,
actual original/candidate SAB via the activation bridge (CarSpecificEvents, VehicleEvents,
StateMachine, IQControlsLayer gate, fault recovery), actual original/candidate
card.controls_update (+ candidate card._sync_startup_arming) with the installed
CarController generating LFA in memory. Publisher, subscriber, diagnostics and Params
are inert/private. Nothing is transmitted. Recorded pandaStates health is replayed as
the candidate's safety observation; recorded motion/torque/EPS fault stay frozen input.
"""
import ast, dataclasses, gzip, hashlib, json, pathlib, re, sys, types


def unclean(x):
  if isinstance(x, dict):
    if set(x) == {'__bytes__'}: return bytes.fromhex(x['__bytes__'])
    return {k: unclean(v) for k, v in x.items()}
  if isinstance(x, list): return [unclean(v) for v in x]
  return x


def fill(obj, data):
  for k, v in data.items():
    if not hasattr(obj, k): raise ValueError('Unexpected IQCarParams field ' + k)
    if dataclasses.is_dataclass(getattr(obj, k)): fill(getattr(obj, k), v)
    else: setattr(obj, k, v)
  return obj


def decode_lfa(d):
  v = int.from_bytes(d, 'little')
  return ((v >> 41) & 0x7ff) - 1024, (v >> 52) & 1, (v >> 16) & 255


def run(payload):
  import iqpilot.common.params as params_module
  from iqpilot.cereal import car, custom, log
  from iqdbc.car import structs, Bus
  from iqdbc.car.can_definitions import CanData
  from iqdbc.car.interfaces import CarInterfaceBase
  from iqdbc.can import CANParser
  from iqpilot.selfdrive.car.helpers import convert_iq_car_control_compact
  from iqpilot.selfdrive.pandad import can_list_to_can_capnp
  original_params = params_module.Params
  metadata = unclean(json.loads(pathlib.Path(payload['metadata']).read_text()))
  fixture = pathlib.Path(payload['fixture'])
  assert hashlib.sha256(fixture.read_bytes()).hexdigest() == metadata['fixture_sha256']
  origin = metadata['origin_ns']
  window = payload.get('trace_window_s', [0.0, 125.0])
  sources = {k: pathlib.Path(payload[k]).read_bytes() for k in
             ['original_carstate', 'candidate_carstate', 'original_card', 'candidate_card',
              'candidate_sab', 'sab_bridge', 'controller']}
  identities = {k: {'path': payload[k], 'sha256': hashlib.sha256(v).hexdigest()} for k, v in sources.items()}

  private_root = pathlib.Path(payload['private_params']).resolve()
  assert '/data/params' not in str(private_root) and '/persist/params' not in str(private_root)
  private_root.mkdir(parents=True, exist_ok=True)
  params = original_params(str(private_root))
  copied = []
  for ent in metadata['params']['entries']:
    if 'value' not in ent or not re.fullmatch(r'[A-Za-z0-9_]+', ent['key']): continue
    p = pathlib.Path(params.get_param_path(ent['key'])).resolve()
    assert p.is_relative_to(private_root)
    p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(ent['value']); copied.append(ent['key'])
  params.put_bool('ControlsReady', False)

  def isolated_params(*a, **kw):
    if a or kw: raise RuntimeError('Unexpected Params path')
    return params
  aliases = []
  for name, loaded in list(sys.modules.items()):
    if name.startswith(('iqpilot.', 'iqdbc.')) and getattr(loaded, 'Params', None) is original_params:
      aliases.append(loaded); loaded.Params = isolated_params
  params_module.Params = isolated_params
  try:
    CP = structs.CarParams.new_message(**metadata['carParams'])
    CP_IQ = fill(structs.IQCarParams(), metadata['iqCarParams'])
    bridge_module = types.ModuleType('isolated_sab_bridge')
    exec(compile(sources['sab_bridge'], payload['sab_bridge'], 'exec'), bridge_module.__dict__)
    bm = types.ModuleType('isolated_candidate_behavior'); bm.__file__ = payload['candidate_sab']
    sys.modules[bm.__name__] = bm
    exec(compile(sources['candidate_sab'], payload['candidate_sab'], 'exec'), bm.__dict__)

    clock = {'ns': origin}
    fake_time = types.SimpleNamespace(monotonic=lambda: clock['ns'] / 1e9, monotonic_ns=lambda: clock['ns'])

    class SM:
      frame = 0
      recv_frame = {'carControl': 0}
      valid = {'modelV2': False, 'pandaStates': True}
      logMonoTime = {'pandaStates': 0}
      states = []
      def all_alive(self, services): return True
      def __getitem__(self, k): return self.states if k == 'pandaStates' else None

    runs = {}
    for label in ('original', 'candidate'):
      cs_mod = types.ModuleType('isolated_carstate_' + label); cs_mod.__file__ = payload[label + '_carstate']
      exec(compile(sources[label + '_carstate'], payload[label + '_carstate'], 'exec'), cs_mod.__dict__)
      CS = cs_mod.CarState(CP, CP_IQ)
      parsers = CS.get_can_parsers(CP, CP_IQ)
      cc_mod = types.ModuleType('isolated_controller_' + label); cc_mod.__file__ = payload['controller']
      exec(compile(sources['controller'], payload['controller'], 'exec'), cc_mod.__dict__)
      CC = cc_mod.CarController({bus: p.dbc_name for bus, p in parsers.items()}, CP, CP_IQ)
      assert (CC.params.STEER_MAX, CC.params.STEER_DELTA_UP, CC.params.STEER_DELTA_DOWN) == (270, 2, 3)
      CI = types.SimpleNamespace(CS=CS, CC=CC, can_parsers=parsers, v_ego_cluster_seen=False)
      CI.apply = lambda *a, CI=CI, **kw: CarInterfaceBase.apply(CI, *a, **kw)
      init_calls = []
      CI.init = lambda *a, init_calls=init_calls: init_calls.append(clock['ns'])
      bridge = bridge_module.Bridge(CP, CP_IQ, params, bm.SteeringAssistanceBehavior if label == 'candidate' else None)
      params.put_bool('ControlsReady', False)
      events = []
      class ParamsProxy:
        def put_bool_nonblocking(self, key, value, events=events):
          assert key == 'ControlsReady' and value is True
          params.put_bool('ControlsReady', True)
          events.append({'t_s': (clock['ns'] - origin) / 1e9, 'event': 'ControlsReady'})
      sm = SM(); sm.states = []; sm.logMonoTime = {'pandaStates': 0}; sm.recv_frame = {'carControl': 0}
      sent = []
      def publish(service, message, sent=sent, CS=CS):
        assert service == 'sendcan'
        with log.Event.from_bytes(message) as ev:
          for f in ev.sendcan:
            if int(f.address) == 0x12a:
              tq, rq, ctr = decode_lfa(bytes(f.dat))
              sent.append({'t_s': (clock['ns'] - origin) / 1e9, 'bus': int(f.src), 'torque': tq, 'request': rq, 'counter': ctr})
      g = {'time': fake_time, 'DT_CTRL': .01, 'REPLAY': True, 'car': car, 'custom': custom, 'log': log,
           'convert_iq_car_control_compact': convert_iq_car_control_compact, 'can_list_to_can_capnp': can_list_to_can_capnp,
           'PerfSample': lambda **kw: types.SimpleNamespace(**kw),
           'CARD_FLAG_FALLBACK_ACTIVE': 1, 'CARD_FLAG_CARSTATE_ALIVE': 2, 'CARD_FLAG_SENDCAN_GAP': 4,
           'CARD_SENDCAN_GAP_WARN_US': 20000, 'CARD_SENDCAN_GAP_ERROR_US': 60000, 'getattr': getattr}
      tree = ast.parse(sources[label + '_card'])
      cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Car')
      methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('controls_update', '_sync_startup_arming')]
      exec(compile(ast.fix_missing_locations(ast.Module(body=methods, type_ignores=[])), payload[label + '_card'], 'exec'), g)
      card = types.SimpleNamespace(CI=CI, CP=CP, CP_IQ=CP_IQ, initialized_prev=False, can_callbacks=(None, None),
        params=ParamsProxy(), sm=sm, _needs_iq_lead_data=True, pm=types.SimpleNamespace(send=publish),
        _last_sendcan_mono_ns=None, _perf_ring=types.SimpleNamespace(push=lambda *a: None, snapshot=lambda: []),
        _perf=types.SimpleNamespace(emit=lambda *a, **kw: None), CC_prev=car.CarControl.new_message().as_reader(),
        carcontrol_stale_frames=10**9, last_actuators_output=None, can_log_mono_time=origin)
      has_sync = '_sync_startup_arming' in g
      runs[label] = dict(CS=CS, CI=CI, bridge=bridge, card=card, g=g, sm=sm, sent=sent, events=events,
                         init_calls=init_calls, has_sync=has_sync, valid_count=0, avail_mismatch=0, lat_mismatch=0,
                         series=[], pending_hist=[])

    packets = []; ticks = 0; trace = []; recorded_sent = []; nonmonotonic = 0
    for line in gzip.open(fixture, 'rt'):
      row = json.loads(line); kind, t = row[:2]
      if kind == 'can':
        if packets and t < packets[-1][0]: nonmonotonic += 1
        packets.append((t, [CanData(a, bytes.fromhex(h), b) for a, h, b in row[2]])); continue
      if kind == 'sent':
        for a, h, b in row[2]:
          tq, rq, ctr = decode_lfa(bytes.fromhex(h))
          recorded_sent.append({'t_s': (t - origin) / 1e9, 'bus': b, 'torque': tq, 'request': rq})
        continue
      assert kind == 'tick'
      assert all(ct <= t for ct, _ in packets), 'Future CAN input'
      assert all(mt <= t for mt in row[4].values()), 'Future frozen state'
      ticks += 1; s = (t - origin) / 1e9; logged = row[2]; latest = unclean(row[3]); recent_t = row[4]
      clock['ns'] = t
      rec_cc = latest.get('carControl')
      entry = {'t': s, 'logged_available': logged['cruiseState']['available'], 'logged_brake': logged['brakePressed'],
               'logged_latActive': bool(rec_cc and rec_cc.get('latActive')),
               'logged_aol': latest.get('iqState', {}).get('aol', {})}
      for label, R in runs.items():
        CI = R['CI']; CS = R['CS']; card = R['card']; sm = R['sm']
        sm.frame = ticks; sm.recv_frame['carControl'] = ticks; card.can_log_mono_time = t
        if 'pandaStates' in latest:
          if recent_t['pandaStates'] != sm.logMonoTime['pandaStates']:
            sm.states = log.Event.new_message(pandaStates=latest['pandaStates']).pandaStates
            sm.logMonoTime['pandaStates'] = recent_t['pandaStates']
        if R['has_sync']:
          R['g']['_sync_startup_arming'](card, t)
        ret, ret_iq = CarInterfaceBase.update(CI, packets)
        sab = R['bridge'].update(ret, logged, latest)
        R['valid_count'] += int(ret.canValid)
        n_before = len(R['sent'])
        if rec_cc is not None and ret.canValid:
          cc = structs.CarControl.new_message(**rec_cc)
          cc.latActive = sab['latActive']; cc.enabled = sab['long_enabled']; cc.longActive = False
          cc_iq = custom.IQCarControl.new_message()
          R['g']['controls_update'](card, ret, cc.as_reader(), cc_iq.as_reader())
          card.initialized_prev = True
        new = R['sent'][n_before:]
        vals = {'available': bool(ret.cruiseState.available), 'main_enabled': bool(CS.main_enabled),
                'brake': bool(ret.brakePressed), 'canValid': bool(ret.canValid), 'vEgo': round(float(ret.vEgo), 3),
                'ready_count': int(CS.controls_ready_count),
                'parser_invalid': {str(b): int(p.can_invalid_cnt) for b, p in CI.can_parsers.items()},
                'buttonEvents': [b.to_dict() for b in ret.buttonEvents],
                'buttons': list(CI.can_parsers[Bus.pt].vl_all[CS.cruise_btns_msg_canfd]['CRUISE_BUTTONS']),
                'main_btn': list(CI.can_parsers[Bus.pt].vl_all[CS.cruise_btns_msg_canfd]['ADAPTIVE_CRUISE_MAIN_BTN']),
                'sab': sab, 'lfa': [{k: v for k, v in x.items() if k != 't_s'} for x in new],
                'arm_pending': bool(getattr(CS, '_tucson_arm_pending', False)),
                'safety_configured': bool(getattr(CS, '_tucson_safety_configured', False)),
                'handoff_sent': bool(getattr(card, '_startup_handoff_sent', False))}
        entry[label] = vals
        if s >= 10 and vals['available'] != entry['logged_available']: R['avail_mismatch'] += 1
        if s >= 10 and rec_cc is not None and sab['latActive'] != entry['logged_latActive']: R['lat_mismatch'] += 1
        R['series'].append([round(s, 4), int(vals['available']), int(sab['latActive']), int(sab['long_enabled']),
                            int(vals['canValid']), int(vals['brake']),
                            max([abs(x['torque']) for x in new], default=-1), max([x['request'] for x in new], default=-1),
                            int(vals['arm_pending'])])
      if window[0] <= s <= window[1]: trace.append(entry)
      packets = []
    result = {'status': 'route23 full runtime replay completed', 'source': metadata['source'], 'route': metadata['route'],
      'fixture_sha256': metadata['fixture_sha256'], 'ticks': ticks, 'nonmonotonic_can_inside_batch': nonmonotonic,
      'CP': {k: metadata['carParams'][k] for k in ('carFingerprint', 'flags', 'extFlags', 'openpilotLongitudinalControl', 'alternativeExperience')},
      'identities': identities, 'parser_class': str(CANParser), 'parser_module': CANParser.__module__,
      'private_params': str(private_root), 'copied_params_count': len(copied),
      'recorded_sent_lfa': recorded_sent, 'trace': trace, 'series_columns':
        ['t_s', 'available', 'latActive', 'long_enabled', 'canValid', 'brake', 'max_abs_torque(-1=none)', 'max_request(-1=none)', 'arm_pending'],
      'runs': {label: {'valid_count': R['valid_count'], 'availability_mismatch_after10s': R['avail_mismatch'],
                       'latActive_mismatch_after10s': R['lat_mismatch'], 'events': R['events'], 'init_calls': len(R['init_calls']),
                       'generated_lfa_count': len(R['sent']), 'generated_lfa': R['sent'], 'series': R['series']}
               for label, R in runs.items()},
      'limits': 'Actual parser/CarState/CarInterface/CarSpecificEvents/VehicleEvents/StateMachine/SAB/IQControlsLayer/fault recovery/card.controls_update/CarController in memory. Nothing transmitted. Model/DM/system events not reconstructed; recorded motion, actuator torque, EPS fault and pandaStates are frozen input, so the candidate result is permission/output validation, not a physical counterfactual. Publication-time batching is not exact acquisition order.'}
    return result
  finally:
    for loaded in aliases: loaded.Params = original_params
    params_module.Params = original_params


RESULT = run(PAYLOAD)
