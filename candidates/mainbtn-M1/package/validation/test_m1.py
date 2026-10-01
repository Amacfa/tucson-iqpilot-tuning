#!/usr/bin/env python3
"""M1 MAIN-button no-disarm test: rollback vs candidate, stubbed deps (no capnp/device).

a) behavior.py _phase_buttons: Tucson-CP + enabled + MAIN press -> alcDisengaged,
   kill_all False; enabled=False -> nothing; LFA path unchanged; non-Tucson -> same as base.
b) carstate.py: the MAIN-release toggle condition lifted verbatim and exec'd on a fake
   self; deleted latch lines asserted absent (candidate) / present (rollback).
c) py_compile both candidate files.
"""
import sys, os, types, enum, importlib.util, json, re, textwrap

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------- stub framework ----------
class AnyAttr:
  """attr access returns a fresh sentinel; usable as flag int too."""
  def __init__(s, n=''): s._n = n
  def __getattr__(s, k): return AnyAttr(k)
  def __call__(s, *a, **k): return AnyAttr()
  def __eq__(s, o): return isinstance(o, AnyAttr) and s._n == o._n
  def __hash__(s): return hash(s._n)
  def __int__(s): return 0
  def __and__(s, o): return 0
  def __rand__(s, o): return 0
  def __repr__(s): return f'AnyAttr({s._n})'

def mod(name, **attrs):
  m = types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name] = m; return m

# real button enum (distinct values needed for the event loop)
BT = enum.IntEnum('BT', 'decelCruise accelCruise setCruise resumeCruise cancel mainCruise gapAdjustCruise lkas lfaButton')
EventName = AnyAttr('EventName')          # any name -> sentinel

class LaxNS(types.SimpleNamespace):
  def __getattr__(self, k): return AnyAttr(k)
car = types.SimpleNamespace(CarState=LaxNS(ButtonEvent=LaxNS(Type=BT)))
TUCSON = object()  # carFingerprint sentinel

class Flags:  # HyundaiFlags stub
  CANFD = 0x40
  CANFD_ALT_BUTTONS = 0x400
class FlagsIQ:
  HAS_LFA_BUTTON = 0x1
class SafetyIQ:
  pass
CAR = types.SimpleNamespace(HYUNDAI_TUCSON_4TH_GEN=TUCSON)

params_mod = mod('iqpilot.common.params',
                 Params=type('Params', (), {'get': lambda s,*a,**k: None,
                                            'get_bool': lambda s,*a,**k: False,
                                            'get_int': lambda s,*a,**k: 0}),
                 UnknownKeyName=type('UnknownKeyName', (Exception,), {}))
mod('iqpilot.common.constants', CV=AnyAttr())
mod('iqpilot.common.realtime', DT_CTRL=0.01)
mod('iqpilot.common.filter_simple', MyFirstOrder=AnyAttr())
mod('iqpilot.common.params_extra', ParamsExtra=AnyAttr())
mod('iqpilot.selfdrive.selfdrived.events', ET=AnyAttr('ET'))
mod('iqpilot.selfdrive.selfdrived.state', SOFT_DISABLE_TIME=3.0, State=AnyAttr('State'))
def lax2(name, **attrs):
  m = types.ModuleType(name); m.__dict__.update(attrs)
  m.__getattr__ = lambda k: AnyAttr(k)
  sys.modules[name] = m
  return m
iqdbc_car = lax2('iqdbc.car', structs=lax2('iqdbc.car.structs', CarState=car.CarState))
mod('iqdbc.safety', ALTERNATIVE_EXPERIENCE=AnyAttr())
mod('iqdbc.car.hyundai.values', CAR=CAR, HyundaiFlags=Flags,
    HyundaiFlagsIQ=FlagsIQ, HyundaiSafetyFlagsIQ=SafetyIQ)
def lax(name, **attrs):
  m = types.ModuleType(name)
  m.__dict__.update(attrs)
  m.__getattr__ = lambda k: AnyAttr(k)
  sys.modules[name] = m
  return m

log_mod = lax('iqpilot.cereal.log', OnroadEvent=types.SimpleNamespace(EventName=EventName))
custom_mod = lax('iqpilot.cereal.custom',
                 IQOnroadEvent=types.SimpleNamespace(EventName=EventName),
                 IQPlan=types.SimpleNamespace(SpeedLimit=AnyAttr()))
cereal = lax('iqpilot.cereal', log=log_mod, custom=custom_mod)
iqpilot = mod('iqpilot'); mod('iqpilot.common'); mod('iqpilot.selfdrive')
mod('iqpilot.selfdrive.selfdrived'); mod('iqdbc'); mod('iqdbc.car.hyundai')
import iqpilot.common as _c; _c.params = params_mod
sys.modules['iqpilot.selfdrive'].selfdrived = sys.modules['iqpilot.selfdrive.selfdrived']
sys.modules['iqdbc'].car = iqdbc_car
sys.modules['iqdbc.car'].hyundai = sys.modules['iqdbc.car.hyundai']
sys.modules['iqdbc.car.hyundai'].values = sys.modules['iqdbc.car.hyundai.values']
sys.modules['iqpilot'].selfdrive = sys.modules['iqpilot.selfdrive']
sys.modules['iqpilot'].cereal = cereal
sys.modules['iqpilot'].common = sys.modules['iqpilot.common']

def load(path, name):
  spec = importlib.util.spec_from_file_location(name, path)
  m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

res = {}
def chk(name, cond, got=None):
  res[name] = bool(cond); res[name + '_val'] = str(got)[:200]

# ================= (a) behavior.py =================
BE_ROLL = os.path.join(PKG, 'rollback/iqpilot/sab/behavior.py')
BE_CAND = os.path.join(PKG, 'candidate/iqpilot/sab/behavior.py')
try:
  b_roll = load(BE_ROLL, 'beh_roll'); b_cand = load(BE_CAND, 'beh_cand')
  chk('a_behavior_modules_load', True)
except Exception as e:
  chk('a_behavior_modules_load', False, f'{type(e).__name__}: {e}')
  print(json.dumps(res, indent=1, sort_keys=True)); sys.exit(1)

class Evts:
  def __init__(s): s.s = set()
  def add(s, e): s.s.add(e)
  def remove(s, e): s.s.discard(e)
  def has(s, e): return e in s.s
  def contains(s, e): return e in s.s
  def contains_in_list(s, evs): return any(e in s.s for e in evs)

def make_beh(mod, tucson=True, enabled=True, sd_enabled=True):
  b = mod.SteeringAssistanceBehavior.__new__(mod.SteeringAssistanceBehavior)
  b.selfdrive = types.SimpleNamespace(enabled=sd_enabled, enabled_prev=False)
  b.CP = types.SimpleNamespace(
      carFingerprint=TUCSON if tucson else object(),
      openpilotLongitudinalControl=True,
      flags=Flags.CANFD_ALT_BUTTONS | Flags.CANFD,
      brand='hyundai')
  b.CP_IQ = types.SimpleNamespace(flags=0)
  b.events = Evts(); b.events_iq = Evts()
  b.enabled = enabled
  b.hkg_allow = True
  b.main_enabled_toggle = True
  b.no_main_cruise = False
  return b

class BE:
  def __init__(s, t, pressed=True): s.type = t; s.pressed = pressed
def cs_of(btns, avail=True):
  return types.SimpleNamespace(buttonEvents=btns,
                               cruiseState=types.SimpleNamespace(available=avail),
                               lateralAvailable=False, gasPressed=False)

Q_DIS = EventName.alcDisengaged; Q_ENG = EventName.alcEngaged

# a1: Tucson + enabled + MAIN pressed -> candidate emits alcDisengaged, kill_all False; base emits nothing
b = make_beh(b_cand); ka = b._phase_buttons(cs_of([BE(BT.mainCruise)]))
chk('a1_cand_main_emits_disengaged', b.events_iq.contains(Q_DIS) and ka is False,
    (list(map(str, b.events_iq.s)), ka))
b = make_beh(b_roll); ka = b._phase_buttons(cs_of([BE(BT.mainCruise)]))
chk('a1_base_main_silent', not b.events_iq.s and ka is False, (list(map(str, b.events_iq.s)), ka))

# a2: enabled=False -> candidate emits nothing from MAIN
b = make_beh(b_cand, enabled=False); ka = b._phase_buttons(cs_of([BE(BT.mainCruise)]))
chk('a2_cand_main_disabled_silent', not b.events_iq.s and ka is False,
    (list(map(str, b.events_iq.s)), ka))

# a3: LFA pressed while not enabled -> both emit alcEngaged (lateral path unchanged)
for mod, tag in ((b_roll, 'base'), (b_cand, 'cand')):
  b = make_beh(mod, enabled=False)
  b._phase_buttons(cs_of([BE(BT.lfaButton)]))
  chk(f'a3_{tag}_lfa_engages', b.events_iq.contains(Q_ENG), list(map(str, b.events_iq.s)))

# a4: non-Tucson CP -> candidate identical to base for MAIN press
for mod, tag in ((b_roll, 'base'), (b_cand, 'cand')):
  b = make_beh(mod, tucson=False)
  ka = b._phase_buttons(cs_of([BE(BT.mainCruise)]))
  chk(f'a4_{tag}_nontucson_main_silent', not b.events_iq.s and ka is False,
      (list(map(str, b.events_iq.s)), ka))

# a5: helper factored + used by both sites
src = open(BE_CAND).read()
chk('a5_helper_defined_and_shared', src.count('_tucson_guarded') == 3
    and 'def _tucson_guarded(self):' in src, src.count('_tucson_guarded'))
chk('a5_gate_uses_helper', 'guarded = self._tucson_guarded()' in src)

# ================= (b) carstate.py =================
CS_CAND = os.path.join(PKG, 'candidate/artifacts/package_sources/iqdbc/iqdbc/car/hyundai/carstate.py')
CS_ROLL = os.path.join(PKG, 'rollback/artifacts/package_sources/iqdbc/iqdbc/car/hyundai/carstate.py')
cand_src = open(CS_CAND).read(); roll_src = open(CS_ROLL).read()

# b1: deleted latch lines
latch = ("      if self.main_enabled and (bool(self.main_buttons[-1]) or any(main_samples)):\n"
         "        self._tucson_main_off_latched = True")
chk('b1_latch_absent_in_cand', latch not in cand_src)
chk('b1_latch_present_in_roll', latch in roll_src)
chk('b1_gate_stored', 'self._tucson_release_gate = tucson_release_gate' in cand_src)
chk('b1_gate_init', 'self._tucson_release_gate = False' in cand_src)

# b2: lift the toggle block verbatim and exec on a fake self
m = re.search(r'^    if self\.main_buttons\[-1\] != prev_main_buttons.*?print\("main_enabled.*?\)\n',
              cand_src, re.S | re.M)
chk('b2_toggle_block_found', m is not None)
snippet = textwrap.dedent(m.group(0))
chk('b2_snippet_guarded', '_tucson_release_gate' in snippet, snippet[:120])

class FakeSelf:
  def __init__(s, gate, main_enabled):
    s._tucson_release_gate = gate
    s.main_enabled = main_enabled
    s.main_buttons = [0] * 10  # indexable; [-1] used

def run_toggle(prev, cur, gate, me):
  s = FakeSelf(gate, me); s.main_buttons[-1] = cur
  ns = {'self': s, 'prev_main_buttons': prev}
  import io, contextlib
  with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(snippet, '<toggle>', 'exec'), ns)
  return s.main_enabled

chk('b2_gate_armed_main_on_release_stays', run_toggle(1, 0, True, True) is True)
chk('b2_gate_armed_main_off_release_toggles_on', run_toggle(1, 0, True, False) is True)
chk('b2_no_gate_off_release_toggles_off', run_toggle(1, 0, False, True) is False)
chk('b2_no_gate_off_release_toggles_on', run_toggle(1, 0, False, False) is True)
chk('b2_no_edge_no_toggle', run_toggle(1, 1, True, True) is True)

# ================= (c) py_compile =================
for f, tag in ((BE_CAND, 'behavior'), (CS_CAND, 'carstate')):
  try:
    compile(open(f).read(), f, 'exec'); chk(f'c_pycompile_{tag}', True)
  except SyntaxError as e:
    chk(f'c_pycompile_{tag}', False, str(e))

res['all_passed'] = all(v for k, v in res.items() if not k.endswith('_val'))
print(json.dumps(res, indent=1, sort_keys=True))
sys.exit(0 if res['all_passed'] else 1)
