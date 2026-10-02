"""Equivalence test for tune-v6 latcontrol_torque.py.

Execs the v5 (installed) and v6 files with stubbed module deps (custom
__import__ hook), instantiates LatControlTorque via object.__new__ with a
faithful stub attribute set, and drives the real update() over replay frames.

Checks:
  1. v6 with an EMPTY LAT_TUNE_V6 (knobs off) == v5 bit-identical.
  2. v6 split_ff_fb with fb_lat_accel_factor == scheduled factor each frame:
     identical to v5 within 1e-9.
"""
import builtins, json, math, os, sys, types
from collections import deque
from difflib import SequenceMatcher
import numpy as np

DT = 0.01
ROOT = os.path.dirname(os.path.abspath(__file__))
V5 = "/home/ubuntu/tucson/github-record/research/tune-v5-table/package/candidate/iqpilot/selfdrive/controls/lib/latcontrol_torque.py"
V6 = os.path.join(ROOT, "latcontrol_torque.py")


class AnyAttr:
  def __init__(self, *a, **k): pass
  def __call__(self, *a, **k): return AnyAttr()
  def __getattr__(self, k): return AnyAttr()
  def __bool__(self): return False
  def __and__(self, o): return o
  def __int__(self): return 0


class NS:
  def __init__(self, **kw): self.__dict__.update(kw)


class FirstOrderFilter:
  def __init__(self, x0, rc, dt):
    self.x, self.rc, self.dt = x0, rc, dt
    self.alpha = 0.0 if rc <= 0 else dt / (rc + dt)
  def update(self, u):
    self.x += self.alpha * (u - self.x)
    return self.x
  def reset(self, x): self.x = x


def get_friction(x, deadzone, threshold, params):
  return float(np.clip(x, -threshold, threshold)) * params.friction


class PIDController:
  """Faithful replica of iqpilot/common/pid.py (anti-windup + control clip)."""
  def __init__(self, k_p, k_i, rate=100):
    self._k_p = k_p; self._k_i = k_i; self.i_dt = 1.0 / rate
    self.pos_limit = 1e308; self.neg_limit = -1e308
    self.speed = 0.0
    self.p = 0.0; self.i = 0.0; self.d = 0.0; self.f = 0.0; self.control = 0.0
  def set_limits(self, pos_limit, neg_limit):
    self.pos_limit = pos_limit; self.neg_limit = neg_limit
  def update(self, error, error_rate=0.0, speed=0.0, feedforward=0., freeze_integrator=False):
    self.speed = speed
    self.p = float(np.interp(speed, self._k_p[0], self._k_p[1])) * float(error)
    self.d = 0.0
    self.f = feedforward
    if not freeze_integrator:
      i = self.i + 0.15 * self.i_dt * error
      test_control = self.p + i + self.d + self.f
      i_ub = self.i if test_control > self.pos_limit else self.pos_limit
      i_lb = self.i if test_control < self.neg_limit else self.neg_limit
      self.i = float(np.clip(i, i_lb, i_ub))
    control = self.p + self.i + self.d + self.f
    self.control = float(np.clip(control, self.neg_limit, self.pos_limit))
    return self.control


class LatControl:
  supports_legacy_curvature_lookahead = False
  def __init__(self, *a, **k): pass
  def _check_saturation(self, *a, **k): return False
  def reset(self): pass


class _Params:
  def get_bool(self, k): return False


class _Slew:
  enabled = False
  def update(self, t, v, dt): return t
  def reset(self, x): pass


_mod = types.ModuleType
def m(**kw): return _mod('stub') if not kw else types.SimpleNamespace(**kw)

MODULES = {
  'tomllib': m(load=lambda f: {}),
  'importlib.resources': m(files=lambda *a, **k: AnyAttr()),
  'iqpilot.cereal': m(log=AnyAttr(), custom=AnyAttr()),
  'iqdbc.car': m(Bus=AnyAttr(), DT_CTRL=0.01, make_tester_present_msg=AnyAttr(), structs=AnyAttr()),
  'iqdbc.car.carlog': m(carlog=AnyAttr()),
  'iqdbc.car.lateral': m(FRICTION_THRESHOLD=0.3, get_friction=get_friction,
                         apply_driver_steer_torque_limits=AnyAttr(),
                         apply_std_steer_angle_limits=AnyAttr(), common_fault_avoidance=AnyAttr()),
  'iqdbc.car.common.conversions': m(Conversions=AnyAttr()),
  'iqdbc.car.toyota.values': m(ToyotaFlags=AnyAttr()),
  'iqdbc.lvbs.car.interfaces': m(LatControlInputs=AnyAttr()),
  'iqdbc.lvbs.car.iq_lateral': m(get_friction=get_friction),
  'iqpilot.common.basedir': m(BASEDIR='/tmp'),
  'iqpilot.common.constants': m(ACCELERATION_DUE_TO_GRAVITY=9.81),
  'iqpilot.common.filter_simple': m(FirstOrderFilter=FirstOrderFilter),
  'iqpilot.common.params': m(Params=_Params),
  'iqpilot.common.pid': m(PIDController=PIDController),
  'iqpilot.selfdrive.controls.lib.drive_helpers': m(CONTROL_N=10),
  'iqpilot.selfdrive.controls.lib.latcontrol': m(LatControl=LatControl),
  'iqpilot.selfdrive.controls.lib.lateral_acceleration_slew_limiter': m(LateralAccelerationSlewLimiter=lambda *a, **k: _Slew()),
  'iqpilot.selfdrive.iqmodeld.config': m(ModelConstants=AnyAttr()),
  'iqpilot.selfdrive.iqmodeld.parser': m(safe_exp=np.exp),
  'iqpilot.selfdrive.controls.lib.helpers.nav_torque_pulse': m(NavTorquePulseBrain=AnyAttr),
}
# real numpy/math stay real
_real_import = builtins.__import__

def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
  if name in MODULES:
    return MODULES[name]
  try:
    return _real_import(name, globals, locals, fromlist, level)
  except ImportError:
    return m()


def load_class(path):
  g = {'__builtins__': dict(vars(builtins), __import__=fake_import),
       'np': np, 'math': math, 'json': json, 'os': os, 'deque': deque,
       'SequenceMatcher': SequenceMatcher}
  src = open(path).read()
  exec(compile(src, path, 'exec'), g)
  return g['LatControlTorque']


def make_instance(LCT, v6=None, fb_factor=None):
  c = object.__new__(LCT)
  c.dt = DT
  c.torque_params = NS(latAccelFactor=2.95, latAccelOffset=0.0, friction=0.12,
                       steeringAngleDeadzoneDeg=0.0)
  c.torque_from_lateral_accel = lambda la, tp: la / float(tp.latAccelFactor)
  c.lateral_accel_from_torque = lambda tq, tp: tq * float(tp.latAccelFactor)
  c.steer_max = 1.0
  c.hkg_reduced_torque_feedback = False
  c.friction_scale = 1.0
  c.pid = PIDController([[1, 1.5, 2.0, 3.0, 5, 7.5, 10, 15, 30],
                         [250, 120, 65, 30, 11.5, 5.5, 3.5, 2.0, 0.8]], 0.15, rate=1 / DT)
  c._kp_base = [c.pid._k_p[0], list(c.pid._k_p[1])]
  c._fric_err_lp = 0.0
  c.steering_angle_deadzone_deg = 0.0
  c.lat_accel_request_buffer_len = 100
  c.lat_accel_request_buffer = deque([0.] * 100, maxlen=100)
  c.lookahead_frames = 19
  c.jerk_filter = FirstOrderFilter(0.0, 1 / (2 * np.pi * 1.2), DT)
  c.setpoint_lead_enabled = False
  c.setpoint_lead_filter = FirstOrderFilter(0.0, 1.0, DT)
  c.lateral_acceleration_slew_limiter = _Slew()
  c.lat_accel_factor_speed_table = ([8.0, 12.0, 15.0, 25.0], [2.95, 3.45, 4.05, 4.05])
  c.v6 = v6
  if v6 is not None:
    fb0 = fb_factor if fb_factor is not None else v6.get('fb_lat_accel_factor', 2.95)
    c._fb_torque_params = NS(latAccelFactor=fb0,
                             latAccelOffset=0.0, friction=0.12, steeringAngleDeadzoneDeg=0.0)
    c._lat_delay_lp = FirstOrderFilter(0.0, v6['timing'].get('lat_delay_tau', 0.0), DT)
    c._hb_elapsed = None
    c._sp_sign = 0.0
  return c


def nnff_update(CS, VM, pid, params, ff, pid_log, setpoint, measurement, calibrated_pose,
                roll_compensation, fut_la, m2, dead, grav, limited, measured, steer_lim, tq):
  return pid_log, tq


class _PidLog:
  def __init__(self):
    self._d = {}
  def __setattr__(self, k, v):
    if k == '_d': object.__setattr__(self, k, v); return
    self._d[k] = v
  def __getattr__(self, k):
    return self._d.get(k)


def frames():
  d = np.load('/home/ubuntu/tucson/analysis/wobble/drive1_frames.npz', allow_pickle=True)
  n = min(6000, len(d['vEgo']))
  return [dict(v=float(d['vEgo'][k]), des=float(d['dla'][k]), act=bool(d['act'][k]),
               prs=bool(d['prs'][k]), ala=float(d['ala'][k]), delay=0.15) for k in range(n)]


def run(c, fr, fb_match=False):
  c.nnff_assist = NS(update=nnff_update)
  VM = NS(calc_curvature=lambda *a: 0.0)
  params = NS(roll=0.0, angleOffsetDeg=0.0)
  outs = []
  for f in fr:
    if fb_match:
      c._fb_torque_params.latAccelFactor = float(np.interp(f['v'], *c.lat_accel_factor_speed_table))
    cs = NS(vEgo=f['v'], steeringPressed=f['prs'], steeringAngleDeg=0.0)
    tq, _, _ = c.update(f['act'], cs, VM, params, False, f['des'], None, False, f['delay'])
    outs.append(tq)
  return np.array(outs)


def main():
  fr = frames()
  L5 = load_class(V5)
  L6 = load_class(V6)
  base = run(make_instance(L5), fr)

  # 1. knobs off == v5 bit-identical
  off = run(make_instance(L6, v6=None), fr)
  bit_identical = bool(np.array_equal(base, off))

  # 2. only split_ff_fb on, fb factor forced == scheduled each frame -> ~identical
  v6A = {"split_ff_fb": True, "fb_lat_accel_factor": 2.960174,
         "handback": {}, "timing": {"lat_delay_tau": 0.0, "fractional_delay": False}}
  a_out = run(make_instance(L6, v6=v6A), fr, fb_match=True)
  max_diff = float(np.max(np.abs(base - a_out)))

  # 3. configured v6 (table == schedule -> A neutral; timing off; B on)
  v6cfg = {"split_ff_fb": True,
           "fb_lat_accel_factor_speed": ([8.0, 12.0, 15.0, 25.0], [2.95, 3.45, 4.05, 4.05]),
           "handback": {"blend_s": 0.25, "fric_reset_on_reversal": True},
           "timing": {"lat_delay_tau": 0.0, "fractional_delay": False}}
  full = run(make_instance(L6, v6=v6cfg), fr)
  delta = np.abs(full - base)
  top = np.argsort(delta)[::-1][:5]
  top_frames = [dict(i=int(i), v=fr[i]['v'], act=fr[i]['act'], prs=fr[i]['prs'],
                     des=fr[i]['des'], v5=float(base[i]), v6=float(full[i]),
                     d=float(delta[i])) for i in top]
  print(json.dumps({
    "knobs_off_bit_identical": bit_identical,
    "splitA_fb_eq_sched_max_abs_diff": max_diff,
    "splitA_within_1e-9": max_diff < 1e-9,
    "configured_finite": bool(np.all(np.isfinite(full))),
    "configured_max_abs_delta_vs_v5": float(delta.max()),
    "configured_n_delta_gt_1": int((delta > 1.0).sum()),
    "top_delta_frames": top_frames,
  }))


if __name__ == '__main__':
  main()
