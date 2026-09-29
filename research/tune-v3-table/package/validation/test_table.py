import json,re,sys
p='../candidate/iqpilot/selfdrive/controls/lib/latcontrol_torque.py'
s=open(__file__.rsplit('/validation/',1)[0]+'/candidate/iqpilot/selfdrive/controls/lib/latcontrol_torque.py').read()
m=re.search(r'"HYUNDAI_TUCSON_4TH_GEN": \(\[([\d., ]+)\], \[([\d., ]+)\]\)',s)
bp=[float(x) for x in m.group(1).split(',')]; vv=[float(x) for x in m.group(2).split(',')]
assert bp==[8.0,12.0,15.0,25.0] and vv==[2.95,3.20,3.80,3.90], (bp,vv)
assert len(bp)==len(vv)==4
import numpy as np
# monotone nondecreasing, bounds sane
assert all(b<=c for b,c in zip(vv,vv[1:]))
# interp matches the intended refit at bin centers: [10]=3.20,[13.5]=interp(3.2,3.8 at 12,15)=3.5
assert abs(float(np.interp(10,bp,vv))-3.075)<1e-9
assert abs(float(np.interp(13.5,bp,vv))-3.5)<1e-9
assert abs(float(np.interp(20,bp,vv))-3.85)<1e-9
# rest of file identical to rollback except table line
r=open(__file__.rsplit('/validation/',1)[0]+'/rollback/iqpilot/selfdrive/controls/lib/latcontrol_torque.py').read()
mr=re.search(r'"HYUNDAI_TUCSON_4TH_GEN": \(\[[\d., ]+\], \[[\d., ]+\]\)',r)
assert s.replace(m.group(0),'X')==r.replace(mr.group(0),'X')
print(json.dumps({'table_refit_ok':True}))
