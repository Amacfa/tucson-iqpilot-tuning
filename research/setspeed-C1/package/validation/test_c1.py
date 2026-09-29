#!/usr/bin/env python3
"""C1 set-speed re-engage test: stock vs candidate initialize_v_cruise, stubbed deps."""
import sys, os, types, importlib.util
import numpy as np

# ---- minimal stubs for iqpilot/iqdbc deps (no capnp on this box) ----
def enum_mock(*names):
  import enum
  return enum.IntEnum('E', names)

car = types.ModuleType('car')
class _BE:  # button event type namespace
  class Type:
    decelCruise=1; accelCruise=2; setCruise=3; resumeCruise=4; cancel=5; mainCruise=6
    gapAdjustCruise=7; lkas=8
car.CarState = type('CarState', (), {'ButtonEvent': type('ButtonEvent', (), {'Type': _BE.Type})})
custom = types.ModuleType('custom')
custom.IQPlan = type('IQPlan', (), {'SpeedLimit': type('SL', (), {'AssistState': enum_mock('disabled','active','adapting','tempUnavailable')})})
cereal = types.ModuleType('iqpilot.cereal'); cereal.car = car; cereal.custom = custom
common = types.ModuleType('iqpilot.common')
consts = types.ModuleType('iqpilot.common.constants')
consts.CV = type('CV', (), {'MS_TO_KPH': 3.6, 'MS_TO_MPH': 2.23694, 'KPH_TO_MS': 1/3.6, 'MPH_TO_KPH': 1.609344, 'KPH_TO_MPH': 0.621371, 'MPH_TO_MS': 0.44704, 'MS_TO_MPH': 2.236936})
params_mod = types.ModuleType('iqpilot.common.params')
params_mod.Params = lambda *a, **k: type('P', (), {'get': lambda s,*a,**k: None, 'get_bool': lambda s,*a,**k: False, 'get_int': lambda s,*a,**k: 0})()
realtime = types.ModuleType('iqpilot.common.realtime'); realtime.DT_CTRL = 0.01
sd = types.ModuleType('iqpilot.selfdrive'); sdcar = types.ModuleType('iqpilot.selfdrive.car')
li = types.ModuleType('iqpilot.selfdrive.car.long_increments')
li.LongIncrementConfig = dict
li.read_long_increment_config = lambda p: {}
li.resolve_button_step = lambda *a, **k: 1.0
iqdbc = types.ModuleType('iqdbc'); iqdbc_car = types.ModuleType('iqdbc.car')
iqdbc_car.structs = types.SimpleNamespace(CarParams=object, IQCarParams=object)
iqpilot = types.ModuleType('iqpilot'); iqpilot.cereal = cereal
sdcar.long_increments = li
for n, m in [('iqpilot', iqpilot), ('iqpilot.cereal', cereal), ('iqpilot.common', common),
             ('iqpilot.common.constants', consts), ('iqpilot.common.params', params_mod),
             ('iqpilot.common.realtime', realtime), ('iqpilot.selfdrive', sd),
             ('iqpilot.selfdrive.car', sdcar), ('iqpilot.selfdrive.car.long_increments', li),
             ('iqdbc', iqdbc), ('iqdbc.car', iqdbc_car)]:
  sys.modules[n] = m
iqpilot.common = common; iqpilot.selfdrive = sd; sd.car = sdcar; common.params = params_mod

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(path, name):
  spec = importlib.util.spec_from_file_location(name, path)
  m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

ROLL = os.path.join(PKG, 'rollback/iqpilot/selfdrive/car/cruise.py')
CAND = os.path.join(PKG, 'candidate/iqpilot/selfdrive/car/cruise.py')
stock = load(ROLL, 'cruise_stock'); cand = load(CAND, 'cruise_cand')
BT = car.CarState.ButtonEvent.Type

class Evt:
  def __init__(s, t, pressed=True): s.type = t; s.pressed = pressed; s.raw = t
class CS:
  def __init__(s, vEgo, btns=()):
    s.vEgo = vEgo
    s.buttonEvents = [Evt(t) for t in btns]
    s.cruiseState = types.SimpleNamespace(available=True, standstill=False)
    s.gasPressed = False
class CP: pcmCruise = False; brand = 'hyundai'; openpilotLongitudinalControl = True
CPIQ = types.SimpleNamespace()

def helper(mod):
  h = mod.VCruiseHelper(CP(), CPIQ)
  h.v_cruise_min = 8.0  # metric min
  return h

res = {}
def chk(name, cond, got=None): res[name] = bool(cond); res[name+'_val'] = got

# (a) first engage at 4.44 m/s with decelCruise: identical stock vs cand
hs, hc = helper(stock), helper(cand)
cs = CS(4.44, [BT.decelCruise])
hs.initialize_v_cruise(cs, False, False); hc.initialize_v_cruise(cs, False, False)
chk('first_engage_identical', hs.v_cruise_kph == hc.v_cruise_kph, (hs.v_cruise_kph, hc.v_cruise_kph))
chk('first_engage_uses_V_CRUISE_INITIAL_floor', hc.v_cruise_kph == 40, hc.v_cruise_kph)  # stock floors first-engage at V_CRUISE_INITIAL=40 kph

# (b) stale 40 kph, re-engage at 20.5 m/s with decelCruise (SET): cand -> round(73.8)=74, stock keeps 40
for mod, tag in ((stock,'stock'),(cand,'cand')):
  h = helper(mod)
  h.v_cruise_kph = 40; h.v_cruise_cluster_kph = 40; h.v_cruise_kph_last = 40
  h.initialize_v_cruise(CS(20.5, [BT.decelCruise]), False, False)
  globals()['h_'+tag] = h
chk('b_set_reengage_cand_74', h_cand.v_cruise_kph == 74, h_cand.v_cruise_kph)
chk('b_set_reengage_stock_40', h_stock.v_cruise_kph == 40, h_stock.v_cruise_kph)

# (c) re-engage with resumeCruise: keeps last
h = helper(cand); h.v_cruise_kph = 40; h.v_cruise_cluster_kph = 40; h.v_cruise_kph_last = 40
h.initialize_v_cruise(CS(20.5, [BT.resumeCruise]), False, False)
chk('c_resume_keeps_last', h.v_cruise_kph == 40, h.v_cruise_kph)

# (d) re-engage no buttons: unchanged
h = helper(cand); h.v_cruise_kph = 40; h.v_cruise_cluster_kph = 40; h.v_cruise_kph_last = 40
h.initialize_v_cruise(CS(20.5, []), False, False)
chk('d_no_button_unchanged', h.v_cruise_kph == 40, h.v_cruise_kph)

# (e) SET re-engage at 2 m/s -> floored at v_cruise_min=8
h = helper(cand); h.v_cruise_kph = 40; h.v_cruise_cluster_kph = 40; h.v_cruise_kph_last = 40
h.initialize_v_cruise(CS(2.0, [BT.decelCruise]), False, False)
chk('e_set_floor_min', h.v_cruise_kph == 8, h.v_cruise_kph)

# extra: cluster follows set speed on re-engage
h = helper(cand); h.v_cruise_kph = 40; h.v_cruise_cluster_kph = 40; h.v_cruise_kph_last = 40
h.initialize_v_cruise(CS(20.5, [BT.setCruise]), False, False)
chk('f_cluster_follows', h.v_cruise_cluster_kph == 74 and h.v_cruise_kph == 74, (h.v_cruise_kph, h.v_cruise_cluster_kph))

res['all_passed'] = all(v for k, v in res.items() if not k.endswith('_val'))
import json; print(json.dumps(res, indent=1, sort_keys=True))
sys.exit(0 if res['all_passed'] else 1)
