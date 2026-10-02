#!/usr/bin/env python3
"""E1 planner test: e2e turn-accel budget + non-e2e identical to A3-candidate original."""
import builtins, json, math, sys, types
import numpy as np

class AnyAttr:
  def __init__(self, *a, **k): pass
  def __call__(self, *a, **k): return AnyAttr()
  def __getattr__(self, k): return AnyAttr()
  def __bool__(self): return False
  def __int__(self): return 0

def m(**kw): return types.SimpleNamespace(**kw) if kw else types.ModuleType('stub')

CV = types.SimpleNamespace(MS_TO_KPH=3.6, KPH_TO_MS=1/3.6, MPH_TO_KPH=1.609344,
                           KPH_TO_MPH=0.621371, MPH_TO_MS=0.44704, DEG_TO_RAD=math.pi/180)
MC = types.SimpleNamespace(T_IDXS=np.arange(33) * 0.25, IDX_N=33)

class _IQBase:
  def __init__(self, *a, **k): pass
  def update(self, sm): pass
  def update_targets(self, sm, x, vc): return vc
  def is_e2e(self, sm): return True
  def apply_e2e_stop_distance(self, sm, v, a, ss): return a, ss

class _DC:
  def __init__(self, enabled, dt): self.enabled = enabled
  def update(self, *a, **k): return k.get('a_model', 0.0)

class _AB:
  def __init__(self, enabled, dt): pass
  def update(self, *a, **k): return 0.0

MODULES = {
  'iqpilot.cereal.messaging': m(SubMaster=AnyAttr, PubMaster=AnyAttr, new_message=AnyAttr),
  'iqdbc.car.interfaces': m(ACCEL_MIN=-4.0, ACCEL_MAX=2.0),
  'iqpilot.common.constants': m(CV=CV),
  'iqpilot.common.filter_simple': m(FirstOrderFilter=type('FOF', (), {
      '__init__': lambda self, x0, tau, dt: setattr(self, 'x', x0),
      'update': lambda self, v: setattr(self, 'x', v) or v})),
  'iqpilot.common.params': m(Params=AnyAttr, UnknownKeyName=type('U', (Exception,), {})),
  'iqpilot.common.realtime': m(DT_MDL=0.05, DT_CTRL=0.01),
  'iqpilot.selfdrive.iqmodeld.config': m(ModelConstants=MC),
  'iqpilot.selfdrive.controls.lib.longcontrol': m(LongCtrlState=AnyAttr()),
  'iqpilot.selfdrive.controls.lib.longitudinal_mpc_lib.long_mpc': m(
      LongitudinalMpc=AnyAttr, LongitudinalPlanSource=types.SimpleNamespace(cruise='cruise', e2e='e2e', mpc='mpc'),
      T_IDXS=np.arange(33) * 0.25),
  'iqpilot.selfdrive.controls.lib.drive_helpers': m(CONTROL_N=10, DEFAULT_STOPPING_SPEED=0.5,
      get_accel_from_plan=lambda *a, **k: (0.0, False)),
  'iqpilot.selfdrive.car.cruise': m(V_CRUISE_MAX=145, V_CRUISE_UNSET=255),
  'iqpilot.common.swaglog': m(cloudlog=AnyAttr()),
  'iqpilot.common.issue_debug': m(log_issue_limited=lambda *a, **k: None),
  'iqpilot.selfdrive.controls.lib.iq_longitudinal_planner': m(LongitudinalPlannerIQ=_IQBase),
  'iqpilot.selfdrive.controls.lib.accel_boost': m(AccelBoost=_AB),
  'iqpilot.selfdrive.controls.lib.e2e_distance_controller': m(E2EDistanceController=_DC),
}
_real = builtins.__import__
def _reg(name):
  parts = name.split('.')
  for i in range(1, len(parts) + 1):
    p = '.'.join(parts[:i])
    obj = MODULES.get(p, sys.modules.get(p) or types.ModuleType(p))
    sys.modules[p] = obj
    if i > 1:
      setattr(sys.modules['.'.join(parts[:i - 1])], parts[i - 1], obj)
  return sys.modules[name]

def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
  if name in MODULES or name.split('.')[0] in ('iqpilot', 'iqdbc', 'cereal', 'msgq', 'openpilot'):
    _reg(name)
    return sys.modules[name] if fromlist else sys.modules[name.split('.')[0]]
  try:
    return _real(name, globals, locals, fromlist, level)
  except ImportError:
    return AnyAttr()

ROOT = __file__.rsplit('/validation/', 1)[0]
def load(path):
  g = {'__builtins__': dict(vars(builtins), __import__=fake_import),
       '__name__': 'e1_' + path.rsplit('/', 1)[1].split('.')[0],
       'np': np, 'math': math}
  src = open(path).read()
  exec(compile(src, path, 'exec'), g)
  return types.SimpleNamespace(**g)

cand = load(ROOT + '/candidate/iqpilot/selfdrive/controls/lib/longitudinal_planner.py')
orig = load(ROOT + '/rollback/iqpilot/selfdrive/controls/lib/longitudinal_planner.py')

CP = types.SimpleNamespace(steerRatio=13.7, wheelbase=2.756)
res = {}
def chk(name, cond, got=None): res[name] = bool(cond); res[name+'_val'] = got

gca_c, gca_o = cand.get_cruise_accel, orig.get_cruise_accel
JC = cand.J_CRUISE
dt = 0.05

# e2e hard turn: v=5.8, angle=117 deg -> a_x_allowed floor 0.3
a_prev = 0.0
a, ss = gca_c(True, 17.9, 5.8, a_prev, 117.0, CP, dt, -1.2, True)
chk('e2e_turn_first_step_le_floor_plus_jerk', a <= 0.3 + JC * dt + 1e-9, a)
exceeded = 0; a_prev = a
for _ in range(60):
  a, _ = gca_c(True, 17.9, 5.8, a_prev, 117.0, CP, dt, -1.2, True)
  a_prev = a
  if a > 0.3 + 1e-9:
    exceeded += 1
chk('e2e_turn_never_exceeds_floor_3s', exceeded == 0, (a, exceeded))

# same speed, angle=0 -> ramps toward cruise accel like before
a, _ = gca_c(True, 17.9, 5.8, 0.0, 0.0, CP, dt, -1.2, True)
chk('e2e_straight_ramps', 0.0 < a <= JC * dt + 1e-9, a)

# non-e2e identical to original on a grid
diffs = []
for v in [0.5, 5.0, 10.0, 20.0, 30.0]:
  for ang in [0.0, 30.0, 90.0, 117.0, -60.0]:
    for vc in [0.0, 15.0, 25.0]:
      ro = gca_o(False, vc, v, 0.5, ang, CP, dt, -1.2, True)
      rc = gca_c(False, vc, v, 0.5, ang, CP, dt, -1.2, True)
      diffs.append(abs(ro[0] - rc[0]) + abs(float(ro[1]) - float(rc[1])))
chk('none2e_identical_to_A3_base', max(diffs) < 1e-12, max(diffs))

# ---- set-drop coast timer via update() ----
def NS(**k): return types.SimpleNamespace(**k)
def mk_planner():
  CPp = NS(steerRatio=13.7, wheelbase=2.756, openpilotLongitudinalControl=True,
           longitudinalActuatorDelay=0.0)
  p = cand.LongitudinalPlanner(CPp, NS(longitudinalStoppingSpeedOverride=0.0))
  p.forcing_stop = False
  p.exp_speed_conv = False
  p.mpc = NS(status=False, source='e2e', crash_cnt=0,
             v_solution=np.zeros(33), a_solution=np.zeros(33), j_solution=np.zeros(32),
             set_weights=lambda **k: None, set_cur_state=lambda *a: None,
             update=lambda *a, **k: None)
  p.prev_e2e = True
  return p

def mk_sm(v_ego, v_cruise_kph, enabled=True, a_e2e=-1.4):
  mv = NS(position=NS(x=np.zeros(33)), velocity=NS(x=np.zeros(33)),
          acceleration=NS(x=np.zeros(33)),
          meta=NS(disengagePredictions=NS(gasPressProbs=[])),
          action=NS(desiredAcceleration=a_e2e, shouldStop=False))
  return {'carControl': NS(orientationNED=[0, 0, 0], longActive=True),
          'carState': NS(vEgo=v_ego, vCruise=v_cruise_kph, aEgo=0.0, standstill=False,
                         steeringAngleDeg=0.0, gasPressed=False),
          'vehicleParameters': NS(angleOffsetDeg=0.0),
          'controlsState': NS(forceDecel=False, longControlState='pid'),
          'selfdriveState': NS(enabled=enabled, personality=0),
          'radarState': NS(leadOne=NS(status=False, dRel=0), leadTwo=NS(status=False)),
          'modelV2': mv}

V_EGO = 16.0                       # ~36 mph, e2e wants -1.4
V40, V30 = 40 * 1.609344, 30 * 1.609344   # kph

# settle baseline at 40 mph set, then drop to 30 and run ~1 s
p = mk_planner()
for _ in range(10):
  p.update(mk_sm(V_EGO, V40))
for _ in range(20):
  p.update(mk_sm(V_EGO, V30))
chk('drop_floor_active_1s', abs(p.output_a_target - (-0.5)) < 0.15, p.output_a_target)

# same speeds, no drop -> floor not active
p2 = mk_planner()
for _ in range(30):
  p2.update(mk_sm(V_EGO, V30))
chk('nodrop_floor_inactive', p2.output_a_target < -0.9, p2.output_a_target)

# after 5 s the timer expires -> floor gone
p3 = mk_planner()
for _ in range(10):
  p3.update(mk_sm(V_EGO, V40))
for _ in range(110):   # 5.5 s at dt=0.05
  p3.update(mk_sm(V_EGO, V30))
chk('drop_floor_expired_5s', p3.output_a_target < -0.9, (p3.output_a_target, p3._set_drop_timer))

# reset_state (disengaged / vCruise UNSET) zeroes the timer
p4 = mk_planner()
for _ in range(10):
  p4.update(mk_sm(V_EGO, V40))
p4.update(mk_sm(V_EGO, V30))
assert p4._set_drop_timer > 0.0
sm_off = mk_sm(V_EGO, 255, enabled=False)   # V_CRUISE_UNSET -> reset_state
p4.update(sm_off)
chk('reset_zeroes_timer', p4._set_drop_timer == 0.0, p4._set_drop_timer)

res['all_passed'] = all(v for k, v in res.items() if not k.endswith('_val'))
print(json.dumps(res, indent=1, sort_keys=True))
sys.exit(0 if res['all_passed'] else 1)
