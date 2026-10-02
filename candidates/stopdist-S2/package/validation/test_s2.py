#!/usr/bin/env python3
"""S2 STOP_DISTANCE test — lifts COMFORT_BRAKE/STOP_DISTANCE + get_safe_obstacle_distance
from the candidate long_mpc.py and checks the numbers (imports avoided: acados-free text exec)."""
import os, re, sys, json, textwrap

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(PKG, 'candidate/iqpilot/selfdrive/controls/lib/longitudinal_mpc_lib/long_mpc.py')
ROLL = os.path.join(PKG, 'rollback/iqpilot/selfdrive/controls/lib/longitudinal_mpc_lib/long_mpc.py')

res = {}
def chk(n, c, g=None): res[n] = bool(c); res[n+'_val'] = str(g)[:160]

src = open(CAND).read(); rsrc = open(ROLL).read()
chk('stop_distance_4_in_cand', 'STOP_DISTANCE = 4.0' in src)
chk('stop_distance_3_in_roll', 'STOP_DISTANCE = 3.0' in rsrc)
chk('only_one_line_differs', sum(1 for a, b in zip(src.splitlines(), rsrc.splitlines()) if a != b) == 1)

m = re.search(r'^(COMFORT_BRAKE = [\d.]+)\n(STOP_DISTANCE = [\d.]+)\n.*?^(def get_safe_obstacle_distance.*?return .*?)\n',
              src, re.S | re.M)
chk('block_found', m is not None)
snippet = '\n'.join(m.groups())
ns = {}
exec(compile(snippet, '<s2>', 'exec'), ns)
f = ns['get_safe_obstacle_distance']
chk('v0_is_4', f(0.0, 1.45) == 4.0, f(0.0, 1.45))
chk('v10_t145', abs(f(10.0, 1.45) - (20.0 + 14.5 + 4.0)) < 1e-9, f(10.0, 1.45))

res['all_passed'] = all(v for k, v in res.items() if not k.endswith('_val'))
print(json.dumps(res, indent=1, sort_keys=True))
sys.exit(0 if res['all_passed'] else 1)
