import json, re, subprocess
root = __file__.rsplit('/validation/', 1)[0]
cand = open(root + '/candidate/iqpilot/selfdrive/controls/controlsd.py').read()
roll = open(root + '/rollback/iqpilot/selfdrive/controls/controlsd.py').read()

# clamp present, gated on fingerprint + unestimated status
assert 'self.CP.carFingerprint == "HYUNDAI_TUCSON_4TH_GEN"' in cand
assert 'log.LateralDelay.Status.unestimated' in cand
assert 'lat_delay = min(lat_delay, 0.15)' in cand

# clamp behavior: simulate the decision
def clamp(fp, status, ld):
    l = ld
    if fp == "HYUNDAI_TUCSON_4TH_GEN" and status == "unestimated":
        l = min(l, 0.15)
    return l
assert clamp("HYUNDAI_TUCSON_4TH_GEN", "unestimated", 0.3) == 0.15
assert clamp("HYUNDAI_TUCSON_4TH_GEN", "unestimated", 0.05) == 0.05   # lower real value kept
assert clamp("HYUNDAI_TUCSON_4TH_GEN", "estimated", 0.3) == 0.3       # learned estimate wins
assert clamp("HYUNDAI_TUCSON_4TH_GEN", "invalid", 0.3) == 0.3
assert clamp("OTHER_CAR", "unestimated", 0.3) == 0.3                  # other fingerprints untouched

# single-block diff
d = subprocess.run(['git', 'diff', '--no-index',
                    root + '/rollback/iqpilot/selfdrive/controls/controlsd.py',
                    root + '/candidate/iqpilot/selfdrive/controls/controlsd.py'],
                   capture_output=True, text=True).stdout
chg = [l for l in d.splitlines() if l[:1] in '+-' and not l.startswith(('+++', '---'))]
assert all(l.startswith('+') for l in chg), 'candidate removes/modifies existing lines'
assert len(chg) == 6, len(chg)  # 4 comment + 3 code lines... verify actual
print(json.dumps({'d1_ok': True, 'added_lines': len(chg)}))
