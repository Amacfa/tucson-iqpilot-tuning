#!/usr/bin/env python3
"""On-device segment replay through the iqmodeld binary under a fake params prefix.

Usage: replay_seg.py <seg_dir> <bundle_json> <out_json>
Never touches real params: ModelManager_ActiveBundle is set via custom_params
inside the replay OpenpilotPrefix only. Abort-guard: refuses to run if not offroad.
"""
import os, sys, json, copy
sys.path.insert(0, '/data/openpilot')
os.environ.setdefault('FINGERPRINT', 'HYUNDAI_TUCSON_4TH_GEN')

from iqpilot.common.params import Params
if not Params().get_bool('IsOffroad'):
    print(json.dumps({'error': 'device not offroad — aborting'})); sys.exit(2)

from iqpilot.tools.lib.logreader import LogReader
from iqpilot.tools.lib.framereader import FrameReader
from iqpilot.selfdrive.test.process_replay.process_replay import get_process_config, replay_process
from iqpilot.system.manager.process import PythonProcess
from iqpilot.system.manager.process_config import managed_processes

seg, bundle_json, out = sys.argv[1], sys.argv[2], sys.argv[3]
lr = list(LogReader(f'{seg}/rlog.zst'))
bundle = json.load(open(bundle_json))

def _daemon_launcher(*args, **kwargs):
    # child-process entry: neutralize realtime scheduling (no root in replay), then run daemon main
    import iqpilot.common.realtime as rt
    rt.config_realtime_process = lambda *a, **k: None
    import iqpilot.selfdrive.iqmodeld.daemon as mod
    mod.config_realtime_process = lambda *a, **k: None
    mod.main()

# run daemon.py as a PythonProcess (native ./iqmodeld binary lacks the venv env)
if 'iqmodeld_py' not in managed_processes:
    managed_processes['iqmodeld_py'] = PythonProcess(
        'iqmodeld_py', 'iqpilot.selfdrive.iqmodeld.daemon', lambda *a: True)
managed_processes['iqmodeld_py'].launcher = _daemon_launcher
cfg = get_process_config('modeld')
cfg.proc_name = 'iqmodeld_py'
cfg.timeout = 600  # GPU JIT load on first frame is slow

frs = {'roadCameraState': FrameReader(f'{seg}/fcamera.hevc', pix_fmt='nv12')}
if os.path.exists(f'{seg}/ecamera.hevc'):
    frs['wideRoadCameraState'] = FrameReader(f'{seg}/ecamera.hevc', pix_fmt='nv12')

cp = {'ModelManager_ActiveBundle': bundle, 'ModelRunnerTypeCache': 1}
store = {}
try:
    msgs = replay_process(cfg, lr, frs, custom_params=cp, captured_output_store=store,
                          disable_progress=True)
except Exception as e:
    json.dump({'error': repr(e),
               'stderr': {k: v['err'][-4000:] for k, v in store.items()},
               'stdout': {k: v['out'][-2000:] for k, v in store.items()}}, open(out, 'w'))
    print(json.dumps({'error': repr(e),
                      'stderr_tail': (list(store.values())[0]['err'][-1500:] if store else 'none')}))
    sys.exit(1)

recs = []
for m in msgs:
    if m.which() == 'modelV2':
        v = m.modelV2
        recs.append({
            't': m.logMonoTime,
            'frame': v.frameId,
            'pos_y': [round(x, 4) for x in list(v.position.y)[:10]],
            'pos_x': [round(x, 4) for x in list(v.position.x)[:10]],
            'll1': round(v.laneLines[1].y[0], 4) if len(v.laneLines) > 1 else None,
            'll2': round(v.laneLines[2].y[0], 4) if len(v.laneLines) > 2 else None,
            'probs': [round(p, 3) for p in list(v.laneLineProbs)],
            'desAcc': round(v.action.desiredAcceleration, 4) if hasattr(v, 'action') else None,
            'vel_x': [round(x, 4) for x in list(v.velocity.x)[:6]],
        })
json.dump({'seg': seg, 'records': recs,
           'stderr': {k: v['err'][-2000:] for k, v in store.items()}}, open(out, 'w'))
print(json.dumps({'seg': seg, 'replayed_modelV2': len(recs),
                  'stderr_tail': (list(store.values())[0]['err'][-400:] if store else '')}))
