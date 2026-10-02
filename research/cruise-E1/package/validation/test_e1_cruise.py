#!/usr/bin/env python3
"""E1 cruise test: IQ_ENGAGE_AT_CURRENT_SPEED behaviour + C1-path preserved when False."""
import sys, os, types, importlib.util, json
import numpy as np

def enum_mock(*names):
  import enum
  return enum.IntEnum('E', names)

car = types.ModuleType('car')
class _BE:
  class Type:
    decelCruise=1; accelCruise=2; setCruise=3; resumeCruise=4; cancel=5; mainCruise=6
    gapAdjustCruise=7; lkas=8
car.CarState = type('CarState', (), {'ButtonEvent': type('ButtonEvent', (), {'Type': _BE.Type})})
custom = types.ModuleType('custom')
custom.IQPlan = type('IQPlan', (), {'SpeedLimit': type('SL', (), {'AssistState': enum_mock('disabled','active','adapting','tempUnavailable')})})
cereal = types.ModuleType('iqpilot.cereal'); cereal.car = car; cereal.custom = custom
common = types.ModuleType('iqpilot.common')
consts = types.ModuleType('iqpilot.common.constants')
consts.CV = type('CV', (), {'MS_TO_KPH': 3.6, 'MS_TO_MPH': 2.23694, 'KPH_TO_MS': 1/3.6,
                          'MPH_TO_KPH': 1.609344, 'KPH_TO_MPH': 0.621371,
                          'MPH_TO_MS': 0.44704, 'MS_TO_MPH': 2.236936})
params_mod = types.ModuleType('iqpilot.common.params')
params_mod.Params = lambda *a, **k: type('P', (), {'get': lambda s,*a,**k: None,
                                                 'get_bool': lambda s,*a,**k: False,
                                                 'get_int': lambda s,*a,**k: 0})()
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

ROOT = __file__.rsplit('/validation/', 1)[0]
CAND = ROOT + '/candidate/iqpilot/selfdrive/car/cruise.py'
def load(path, name, engage=None):
  spec = importlib.util.spec_from_file_location(name, path)
  mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
  if engage is not None:
    mod.IQ_ENGAGE_AT_CURRENT_SPEED = engage
  return mod

cand = load(CAND, 'cruise_e1')
cand_off = load(CAND, 'cruise_e1_off', engage=False)
stock = load(ROOT + '/rollback/iqpilot/selfdrive/car/cruise.py', 'cruise_stock')
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

MPH_MS = 0.44704

def helper(mod, metric):
  h = mod.VCruiseHelper(CP(), CPIQ)
  h.v_cruise_min = 8.0
  h._is_metric = metric
  return h

res = {}
def chk(name, cond, got=None): res[name] = bool(cond); res[name+'_val'] = got

def run(mod, mph, metric=False, init=False, btns=()):
  h = helper(mod, metric)
  if init:
    h.v_cruise_kph = 70; h.v_cruise_cluster_kph = 70; h.v_cruise_kph_last = 70
  h.initialize_v_cruise(CS(mph * (1/3.6) if metric else mph * MPH_MS, btns), False, False)
  return h

def to_disp(h, metric):
  return h.v_cruise_kph * (1 if metric else consts.CV.KPH_TO_MPH)

# imperial cases -> displayed mph
chk('e1_19mph_floor25', round(to_disp(run(cand, 19), False)) == 25, to_disp(run(cand, 19), False))
chk('e1_36mph_35', round(to_disp(run(cand, 36), False)) == 35, to_disp(run(cand, 36), False))
chk('e1_2mph_crawl_25', round(to_disp(run(cand, 2), False)) == 25, to_disp(run(cand, 2), False))
chk('e1_33mph_resume_35', round(to_disp(run(cand, 33, init=True, btns=[BT.resumeCruise]), False)) == 35,
    to_disp(run(cand, 33, init=True, btns=[BT.resumeCruise]), False))
chk('e1_47mph_45', round(to_disp(run(cand, 47), False)) == 45, to_disp(run(cand, 47), False))
# metric: 52 kph -> 50
h = run(cand, 52, metric=True)
chk('e1_52kph_50', h.v_cruise_kph == 50.0, h.v_cruise_kph)
# cluster == v_cruise always
h = run(cand, 33, init=True, btns=[BT.resumeCruise])
chk('e1_cluster_eq', h.v_cruise_cluster_kph == h.v_cruise_kph,
    (h.v_cruise_kph, h.v_cruise_cluster_kph))

# IQ_ENGAGE_AT_CURRENT_SPEED=False -> byte-identical C1 behaviour on C1 cases
hs, hc = helper(stock, False), helper(cand_off, False)
cs = CS(4.44, [BT.decelCruise])
hs.initialize_v_cruise(cs, False, False); hc.initialize_v_cruise(cs, False, False)
chk('c1_first_engage_identical', hs.v_cruise_kph == hc.v_cruise_kph, (hs.v_cruise_kph, hc.v_cruise_kph))
h = helper(cand_off, False)
h.v_cruise_kph = 40; h.v_cruise_cluster_kph = 40; h.v_cruise_kph_last = 40
h.initialize_v_cruise(CS(20.5, [BT.decelCruise]), False, False)
chk('c1_set_reengage_74', h.v_cruise_kph == 74, h.v_cruise_kph)
h = helper(cand_off, False)
h.v_cruise_kph = 40; h.v_cruise_cluster_kph = 40; h.v_cruise_kph_last = 40
h.initialize_v_cruise(CS(20.5, [BT.resumeCruise]), False, False)
chk('c1_resume_keeps_last', h.v_cruise_kph == 40, h.v_cruise_kph)
h = helper(cand_off, False)
h.v_cruise_kph = 40; h.v_cruise_cluster_kph = 40; h.v_cruise_kph_last = 40
h.initialize_v_cruise(CS(20.5, []), False, False)
chk('c1_no_button_unchanged', h.v_cruise_kph == 40, h.v_cruise_kph)
h = helper(cand_off, False)
h.v_cruise_kph = 40; h.v_cruise_cluster_kph = 40; h.v_cruise_kph_last = 40
h.initialize_v_cruise(CS(2.0, [BT.decelCruise]), False, False)
chk('c1_set_floor_min', h.v_cruise_kph == 8, h.v_cruise_kph)

res['all_passed'] = all(v for k, v in res.items() if not k.endswith('_val'))
print(json.dumps(res, indent=1, sort_keys=True))
sys.exit(0 if res['all_passed'] else 1)
