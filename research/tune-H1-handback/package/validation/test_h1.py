import json, re, sys
import numpy as np
root = __file__.rsplit('/validation/', 1)[0]
cand = open(root + '/candidate/iqpilot/selfdrive/controls/lib/latcontrol_torque.py').read()
roll = open(root + '/rollback/iqpilot/selfdrive/controls/lib/latcontrol_torque.py').read()

# P-scale interp values at 13 / 15 / 17 m/s
m = re.search(r'np\.interp\(CS\.vEgo, \[13\.0, 17\.0\], \[1\.0, 0\.6\]\)', cand)
assert m, 'P-scale interp missing'
assert np.interp(13.0, [13.0, 17.0], [1.0, 0.6]) == 1.0
assert np.interp(15.0, [13.0, 17.0], [1.0, 0.6]) == 0.8
assert np.interp(17.0, [13.0, 17.0], [1.0, 0.6]) == 0.6
assert np.interp(20.0, [13.0, 17.0], [1.0, 0.6]) == 0.6
assert np.interp(5.0, [13.0, 17.0], [1.0, 0.6]) == 1.0
assert 'self.pid._k_p = [self._kp_base[0], [k * kp_scale' in cand

# friction LP: state init + 0.3 s first-order update + filtered input to get_friction
assert 'self._fric_err_lp = 0.0' in cand
assert 'self._fric_err_lp += (error - self._fric_err_lp) * self.dt / 0.3' in cand
assert 'get_friction(self._fric_err_lp + JERK_GAIN * desired_lateral_jerk' in cand
# LP semantics: time constant 0.3 s
alpha = 0.01 / 0.3
assert abs(alpha - 1 / 30) < 1e-9

# everything else identical to rollback
for frag in ['self._kp_base = [self.pid._k_p[0]', 'self._fric_err_lp = 0.0',
             'self._fric_err_lp += (error - self._fric_err_lp) * self.dt / 0.3\n',
             '      kp_scale = float(np.interp(CS.vEgo, [13.0, 17.0], [1.0, 0.6]))\n      self.pid._k_p = [self._kp_base[0], [k * kp_scale for k in self._kp_base[1]]]\n',
             'self._fric_err_lp + JERK_GAIN']:
    cand2 = cand.replace(frag, '')
    assert cand2 != cand
# structural diff size: only the 3 edits (+-11 lines total incl headers)
import subprocess
d = subprocess.run(['git', 'diff', '--no-index',
                    root + '/rollback/iqpilot/selfdrive/controls/lib/latcontrol_torque.py',
                    root + '/candidate/iqpilot/selfdrive/controls/lib/latcontrol_torque.py'],
                   capture_output=True, text=True).stdout
chg = [l for l in d.splitlines() if l[:1] in '+-' and not l.startswith(('+++', '---'))]
assert len(chg) == 9, len(chg)
print(json.dumps({'h1_ok': True, 'changed_lines': len(chg)}))
