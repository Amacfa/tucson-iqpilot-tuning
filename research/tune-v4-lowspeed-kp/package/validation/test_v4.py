import json, re, subprocess
import numpy as np
root = __file__.rsplit('/validation/', 1)[0]
cand = open(root + '/candidate/iqpilot/selfdrive/controls/lib/latcontrol_torque.py').read()
roll = open(root + '/rollback/iqpilot/selfdrive/controls/lib/latcontrol_torque.py').read()

# v4 kp_scale interp: 0.7 flat below 13, blending to 0.6 at 17
m = re.search(r'np\.interp\(CS\.vEgo, \[13\.0, 17\.0\], \[0\.7, 0\.6\]\)', cand)
assert m, 'v4 P-scale interp missing'
for v, want in [(5.0, 0.7), (13.0, 0.7), (15.0, 0.65), (17.0, 0.6), (25.0, 0.6)]:
    assert abs(float(np.interp(v, [13.0, 17.0], [0.7, 0.6])) - want) < 1e-9, (v, want)
assert 'self.pid._k_p = [self._kp_base[0], [k * kp_scale' in cand
# rollback retains H1 shape
assert re.search(r'np\.interp\(CS\.vEgo, \[13\.0, 17\.0\], \[1\.0, 0\.6\]\)', roll)
# H1 features preserved in candidate
for frag in ['self._kp_base = [self.pid._k_p[0]', 'self._fric_err_lp = 0.0',
             'self._fric_err_lp += (error - self._fric_err_lp) * self.dt / 0.3',
             'self._fric_err_lp + JERK_GAIN']:
    assert frag in cand
# diff is exactly the 2-line change (comment + interp values)
d = subprocess.run(['git', 'diff', '--no-index',
                    root + '/rollback/iqpilot/selfdrive/controls/lib/latcontrol_torque.py',
                    root + '/candidate/iqpilot/selfdrive/controls/lib/latcontrol_torque.py'],
                   capture_output=True, text=True).stdout
chg = [l for l in d.splitlines() if l[:1] in '+-' and not l.startswith(('+++', '---'))]
assert len(chg) == 4, chg
print(json.dumps({'v4_ok': True, 'changed_lines': len(chg)}))
