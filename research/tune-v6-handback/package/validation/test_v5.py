import json, re, subprocess
import numpy as np
root = __file__.rsplit('/validation/', 1)[0]
cand = open(root + '/candidate/iqpilot/selfdrive/controls/lib/latcontrol_torque.py').read()
roll = open(root + '/rollback/iqpilot/selfdrive/controls/lib/latcontrol_torque.py').read()

# v5 table values + monotonicity + interp spot checks
m = re.search(r'"HYUNDAI_TUCSON_4TH_GEN": \(\[8\.0, 12\.0, 15\.0, 25\.0\], \[2\.95, 3\.45, 4\.05, 4\.05\]\)', cand)
assert m, 'v5 table missing'
bp, vals = [8.0, 12.0, 15.0, 25.0], [2.95, 3.45, 4.05, 4.05]
assert vals == sorted(vals)
for v, want in [(8.0, 2.95), (10.0, 3.20), (12.0, 3.45), (15.0, 4.05), (20.0, 4.05), (30.0, 4.05)]:
    assert abs(float(np.interp(v, bp, vals)) - want) < 1e-9, (v, want)
# rollback retains v4 table
assert '[2.95, 3.20, 3.80, 3.90]' in roll
# v4 + H1 features preserved in candidate
for frag in ['np.interp(CS.vEgo, [13.0, 17.0], [0.7, 0.6])',
             'self._kp_base = [self.pid._k_p[0]', 'self._fric_err_lp = 0.0',
             'self._fric_err_lp += (error - self._fric_err_lp) * self.dt / 0.3',
             'self._fric_err_lp + JERK_GAIN']:
    assert frag in cand, frag
# diff is exactly the table line
d = subprocess.run(['git', 'diff', '--no-index',
                    root + '/rollback/iqpilot/selfdrive/controls/lib/latcontrol_torque.py',
                    root + '/candidate/iqpilot/selfdrive/controls/lib/latcontrol_torque.py'],
                   capture_output=True, text=True).stdout
chg = [l for l in d.splitlines() if l[:1] in '+-' and not l.startswith(('+++', '---'))]
assert len(chg) == 2, chg
print(json.dumps({'v5_ok': True, 'changed_lines': len(chg)}))
