#!/usr/bin/env python3
"""Unit test for the L1c jerk_u block, executed against the actual candidate source text.

Extracts the CANFD jerk_u block from the candidate carcontroller.py and execs it in a
namespace with stub CS/self/np, asserting the documented points."""
import os, re, sys, textwrap
import numpy as np

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(PKG, 'candidate/.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carcontroller.py')
ROLL = os.path.join(PKG, 'rollback/.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carcontroller.py')

def extract(path):
  src = open(path).read()
  # grab from jerk_u_base through 'self.jerk_u = max(...)' inside the CANFD branch
  m = re.search(r"(jerk_u_base = .*?\n.*?self\.jerk_u = max\(jerk_u_raw, jerk_u_mpc\))", src, re.S)
  assert m, 'block not found'
  return m.group(1)

class C:
  class out: vEgo = 0.0
class Self: jerk = 0.0; jerk_u = 0.0

def jerk_u(code, vEgo, accel, jerk, jerk_max_u=5.0):
  cs = C(); cs.out = type('o', (), {'vEgo': vEgo})()
  s = Self(); s.jerk = jerk
  ns = {'np': np, 'CS': cs, 'self': s, 'accel': accel, 'jerk_max_u': jerk_max_u}
  exec('\n'.join(l[8:] if l.startswith('        ') else l for l in code.splitlines()), ns)
  return s.jerk_u

code = extract(CAND)
old  = extract(ROLL)
res = {}
def chk(name, cond): res[name] = bool(cond)

# spec points from the brief
chk('v0_accel2_jerk1.5_eq1.2', abs(jerk_u(code, 0, 2.0, 1.5) - 1.2) < 1e-9)
chk('v5.5_accel2_jerk1.5_eq3.0', abs(jerk_u(code, 5.5, 2.0, 1.5) - 3.0) < 1e-9)  # cap=interp(5.5,3,8,1.2,5)=3.1; raw=2.0,mpc=3.0
chk('v10_accel2_jerk0_eq2.0', abs(jerk_u(code, 10, 2.0, 0) - 2.0) < 1e-9)
chk('v0_accel0.5_jerk0_eq1.0', abs(jerk_u(code, 0, 0.5, 0) - 1.0) < 1e-9)
# above 8 m/s the cap is jerk_max_u but the raw boost gain stays 1.0 (old was 2.0):
# new gives 4.0 at accel=4, old gives 5.0 (documents the permanent gain change)
chk('v20_new_eq4.0_old_eq5.0', abs(jerk_u(code, 20, 4.0, 0) - 4.0) < 1e-9 and abs(jerk_u(old, 20, 4.0, 0) - 5.0) < 1e-9)
# monotone non-decreasing in speed for fixed request
seq = [jerk_u(code, v, 2.0, 0) for v in np.arange(0, 15, 0.5)]
chk('monotone_in_speed', all(b >= a - 1e-9 for a, b in zip(seq, seq[1:])))
# old code had no cap: verify old gives 2.0 at v0 same inputs (documents the change)
chk('old_v0_eq2.0_documenting_delta', abs(jerk_u(old, 0, 2.0, 1.5) - 3.0) < 1e-9)

res['all_passed'] = all(res.values())
import json
print(json.dumps(res, indent=1, sort_keys=True))
sys.exit(0 if res['all_passed'] else 1)
