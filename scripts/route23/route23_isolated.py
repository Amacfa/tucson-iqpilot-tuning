import json as _json
from pathlib import Path as _P
EXPECTED_HEAD='0b8c190c59637d10ccd76525f6685c7d3b964264'
PAYLOAD=_json.loads(_P('/tmp/route23/payload.json').read_text())
RUNNER="import tempfile,base64,hashlib,gzip\nfrom pathlib import Path\nimport json\nwith tempfile.TemporaryDirectory(prefix='iq-warning-validation-',dir='/tmp') as isolated_dir:\n original_payload=PAYLOAD\n payload={}\n for key,entry in original_payload['files'].items():\n  dest=Path(isolated_dir)/entry['name'];dest.parent.mkdir(parents=True,exist_ok=True)\n  data=base64.b64decode(entry['data'])\n  if entry.get('gzip'):data=gzip.decompress(data)\n  assert hashlib.sha256(data).hexdigest()==entry['sha256'];dest.write_bytes(data);payload[key]=str(dest)\n payload['private_params']=str(Path(isolated_dir)/'params')\n payload['controller']=original_payload['controller_device_path']\n payload['trace_window_s']=[0.0,125.0]\n PAYLOAD=payload\n exec(compile(original_payload['runner'],'<native-candidate-runner>','exec'),globals())\nRESULT['isolated_files_removed']=not Path(isolated_dir).exists()\n"
"""Isolated non-actuating device wrapper. Runner must set RESULT; never launch managers."""
import os,sys,time,json,hashlib,subprocess,traceback,datetime
from pathlib import Path
os.chdir('/data/openpilot');os.environ['PWD']='/data/openpilot';sys.path.insert(0,'/data/openpilot')
from iqpilot.cereal import messaging
from iqpilot.common.params import Params
LIVE_PARAMS=Params()
PROTECTED_KEYS=['CarPlatformBundle','AolEnabled','AolMainCruiseAllowed','AolUnifiedEngagementMode','AolSteeringMode','LateralManeuverMode','AolPauseOnSteeringOverride','AutoEngage','IQHkgReducedTorqueFeedback','NeuralNetworkFeedForward','IQLateralAccelSlew','CustomSteerMax','CustomSteerDeltaUp','CustomSteerDeltaDown','CarParamsPersistent','IQCarParamsPersistentV2','CalibrationParams','LiveTorqueParameters','IQSteerDelayCache','IQLiveSteerDelay','OpenpilotEnabledToggle']
PROTECTED_FILES=['iqpilot/selfdrive/controls/lib/latcontrol_torque.py','iqpilot/selfdrive/car/card.py','iqpilot/selfdrive/pandad/panda_safety.cc','iqpilot/selfdrive/pandad/pandad.cc','iqpilot/selfdrive/pandad/pandad','.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carstate.py','.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carcontroller.py','.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/hyundaicanfd.py']
def digest(path):
 p=Path(path);return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def snapshot():
 return {'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'boot':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'files':{p:digest(p) for p in PROTECTED_FILES},'params':{k:digest(Path('/data/params/d')/k) for k in PROTECTED_KEYS}}
sm=messaging.SubMaster(['deviceState','pandaStates','managerState'])
def guard_parked():
 end=time.monotonic()+2.2
 while time.monotonic()<end:sm.update(100)
 ages={s:time.monotonic()-sm.recv_time[s] for s in ['deviceState','pandaStates','managerState']}
 assert max(ages.values())<2.1,('stale telemetry',ages)
 assert all(sm.valid[x] for x in ['deviceState','pandaStates','managerState']), 'Invalid parked telemetry'
 assert not LIVE_PARAMS.get_bool('IsOnroad') and not sm['deviceState'].started
 assert len(sm['pandaStates'])>0
 assert all(not(p.ignitionLine or p.ignitionCan or p.controlsAllowed) for p in sm['pandaStates'])
 assert not any(p.running for p in sm['managerState'].processes if p.name in ['card','controlsd'])
 return {'ignition_off':True,'controls_allowed':False,'ages_seconds':ages}
before=snapshot();assert before['head']==EXPECTED_HEAD
preflight=guard_parked()
def deny_publish(*a,**kw):raise AssertionError('Publishing prohibited in isolated validation')
messaging.PubMaster=deny_publish;messaging.pub_sock=deny_publish
# A normal module import may read local identity but may not make an external connection.
import socket
original_connect=socket.socket.connect
def deny_network(self,address):
 if self.family in (socket.AF_INET,socket.AF_INET6):raise AssertionError('Network prohibited in isolated validation')
 return original_connect(self,address)
socket.socket.connect=deny_network
RESULT={};error=None
try:exec(compile(RUNNER,'<isolated-warning-validation>','exec'),globals())
except Exception:error=traceback.format_exc()
postflight=guard_parked();after=snapshot()
assert before==after,('protected state changed',before,after)
report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'preflight':preflight,'postflight':postflight,'before':before,'after':after,'protected_state_unchanged':True,'result':RESULT,'error':error}
print('\nISOLATED_RESULT='+json.dumps(report,default=str))
if error:raise SystemExit(1)
