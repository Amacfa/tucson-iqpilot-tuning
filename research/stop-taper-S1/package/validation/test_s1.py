#!/usr/bin/env python3
"""S1: verify the candidate file has exactly the intended constant deltas and that
settle() behaves identically outside the changed region (lead gating, anti-creep,
emergency, jerk step)."""
import json, py_compile, sys, os
rel='iqpilot/selfdrive/controls/lib/smooth_stops.py'
base=os.path.join(os.path.dirname(__file__),'..')
cand=open(os.path.join(base,'candidate',rel)).read()
orig=open(os.path.join(base,'rollback',rel)).read()
assert 'SETTLE_DECEL = 1.00' in cand and 'SETTLE_DECEL = 0.80' not in cand
assert 'TAPER_SPEED = 0.6' in cand
assert 'SETTLE_DECEL = 0.80' in orig and 'TAPER_SPEED = 1.0' in orig
# identical outside the two lines
cl=[l for l in cand.splitlines() if 'SETTLE_DECEL =' not in l and 'TAPER_SPEED =' not in l]
ol=[l for l in orig.splitlines() if 'SETTLE_DECEL =' not in l and 'TAPER_SPEED =' not in l]
assert cl==ol, 'more than constants changed'
# untouched safety terms present
for k in ('STOP_KISS_DECEL = 0.25','STOP_GAP_MARGIN = 3.0','MIN_GAP_BUDGET = 0.5',
          'ANTI_CREEP_RATE = 0.50','SETTLE_JERK = 2.5','EMERGENCY_DECEL = 3.0'):
    assert k in cand, k
py_compile.compile(os.path.join(base,'candidate',rel), doraise=True)
print(json.dumps({'s1_ok':True,'changed_lines':2}))
