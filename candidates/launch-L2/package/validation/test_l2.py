#!/usr/bin/env python3
"""L2 standstill launch-cap test — execs the actual candidate accel block on a fake CS/self.

Extracts:
    accel = float(np.clip(actuators.accel, ACCEL_MIN, ACCEL_MAX))
    if CS.out.standstill:
      accel = min(accel, LAUNCH_HOLD_ACCEL_MAX)
from candidate/carcontroller.py and runs it. Assumes the constant and gate text exist."""
import os, re, sys, json, textwrap, types
import numpy as np

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(PKG, 'candidate/.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carcontroller.py')
ROLL = os.path.join(PKG, 'rollback/.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carcontroller.py')

res = {}
def chk(n, c, g=None): res[n] = bool(c); res[n+'_val'] = str(g)[:160]

src = open(CAND).read(); rsrc = open(ROLL).read()

# structure assertions
chk('const_present', 'LAUNCH_HOLD_ACCEL_MAX = 1.0' in src)
chk('const_absent_in_rollback', 'LAUNCH_HOLD_ACCEL_MAX' not in rsrc)
m = re.search(r'^    accel = float\(np\.clip\(actuators\.accel.*?accel = min\(accel, LAUNCH_HOLD_ACCEL_MAX\)\n',
              src, re.S | re.M)
chk('cap_block_found', m is not None)
snippet = textwrap.dedent(m.group(0))

# behavioural: exec snippet on fakes
def run(accel_req, standstill):
  actuators = types.SimpleNamespace(accel=accel_req)
  CS = types.SimpleNamespace(out=types.SimpleNamespace(standstill=standstill))
  ns = {'np': np, 'actuators': actuators, 'CS': CS,
        'CarControllerParams': types.SimpleNamespace(ACCEL_MIN=-3.5, ACCEL_MAX=2.0),
        'LAUNCH_HOLD_ACCEL_MAX': 1.0}
  exec(compile(snippet, '<l2>', 'exec'), ns)
  return ns['accel']

chk('standstill_caps_2_to_1', run(2.0, True) == 1.0, run(2.0, True))
chk('rolling_passes_2', run(2.0, False) == 2.0, run(2.0, False))
chk('negative_unchanged_standstill', run(-1.5, True) == -1.5, run(-1.5, True))
chk('sub_cap_unchanged', run(0.5, True) == 0.5, run(0.5, True))
chk('accel_min_respected', run(-5.0, True) == -3.5, run(-5.0, True))

res['all_passed'] = all(v for k, v in res.items() if not k.endswith('_val'))
print(json.dumps(res, indent=1, sort_keys=True))
sys.exit(0 if res['all_passed'] else 1)
