"""Build the device-side isolated route23 validation bundle (payload.json + driver script)."""
import base64, gzip, hashlib, json
from pathlib import Path

R = Path(__file__).resolve().parent
PKG = Path('/home/ubuntu/tucson/analysis/tucson-warning-arming-0b8c190c/package')
INTEG = Path('/home/ubuntu/tucson/integ')
EXPECTED_HEAD = '0b8c190c59637d10ccd76525f6685c7d3b964264'
DEVICE_CONTROLLER = '/data/iqpilot/.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carcontroller.py'

files = {
  'original_carstate': PKG / 'rollback/artifacts/package_sources/iqdbc/iqdbc/car/hyundai/carstate.py',
  'candidate_carstate': PKG / 'candidate/artifacts/package_sources/iqdbc/iqdbc/car/hyundai/carstate.py',
  'original_card': PKG / 'rollback/iqpilot/selfdrive/car/card.py',
  'candidate_card': PKG / 'candidate/iqpilot/selfdrive/car/card.py',
  'candidate_sab': PKG / 'candidate/iqpilot/sab/behavior.py',
  'sab_bridge': INTEG / 'activation/sab_bridge.py',
  'fixture': R / 'route23-fixture-pubtime.jsonl.gz',
  'metadata': R / 'route23-metadata-pubtime.json',
}
out = {'runner': (R / 'runtime_arming_runner.py').read_text(), 'files': {}, 'controller_device_path': DEVICE_CONTROLLER}
for k, p in files.items():
  b = p.read_bytes(); gz = p.suffix == '.json'
  out['files'][k] = {'name': f'{k}/{p.name}', 'sha256': hashlib.sha256(b).hexdigest(),
                     'data': base64.b64encode(gzip.compress(b, mtime=0) if gz else b).decode(), 'gzip': gz}
(R / 'payload.json').write_text(json.dumps(out))

staged = (INTEG / 'device/staged_runner.py').read_text()
# The installed controller is read in place (identity recorded by the runner); everything else is staged under /tmp.
staged = staged.replace(" payload['private_params']=str(Path(isolated_dir)/'params')",
                        " payload['private_params']=str(Path(isolated_dir)/'params')\n payload['controller']=original_payload['controller_device_path']\n payload['trace_window_s']=[0.0,125.0]")
assert "payload['controller']" in staged
guard = (INTEG / 'device/guard.py').read_text()
header = ("import json as _json\nfrom pathlib import Path as _P\n"
          f"EXPECTED_HEAD={EXPECTED_HEAD!r}\n"
          "PAYLOAD=_json.loads(_P('/tmp/route23/payload.json').read_text())\n"
          f"RUNNER={staged!r}\n")
(R / 'route23_isolated.py').write_text(header + guard)
print(json.dumps({k: v['sha256'] for k, v in out['files'].items()}, indent=1))
print('payload bytes', (R / 'payload.json').stat().st_size, 'driver sha256', hashlib.sha256((R / 'route23_isolated.py').read_bytes()).hexdigest())
