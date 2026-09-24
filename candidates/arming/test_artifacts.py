from pathlib import Path
import tempfile,subprocess,hashlib,json,shutil
p=Path(__file__).resolve().parent;m=json.loads((p/'manifest.json').read_text())
with tempfile.TemporaryDirectory(prefix='iq-warning-patch-roundtrip-') as t:
 r=Path(t)
 for e in m['files']:
  rel=e['path']
  for sub,key in [('candidate','candidate_sha256'),('rollback','original_sha256')]:
   f=p/sub/rel;assert hashlib.sha256(f.read_bytes()).hexdigest()==e[key]
  if rel.endswith(('.py','.cc')) and not rel.startswith('.venv'):
   f=r/rel;f.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p/'rollback'/rel,f)
 subprocess.run(['git','apply','--check',str(p/'forward.patch')],cwd=r,check=True)
 subprocess.run(['git','apply',str(p/'forward.patch')],cwd=r,check=True)
 for e in m['files']:
  if (r/e['path']).is_file():assert hashlib.sha256((r/e['path']).read_bytes()).hexdigest()==e['candidate_sha256']
 subprocess.run(['git','apply',str(p/'reverse.patch')],cwd=r,check=True)
 for e in m['files']:
  if (r/e['path']).is_file():assert hashlib.sha256((r/e['path']).read_bytes()).hexdigest()==e['original_sha256']
for rel in ['candidate','rollback']:
 a=p/rel/'artifacts/package_sources/iqdbc/iqdbc/car/hyundai/carstate.py';b=p/rel/'.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carstate.py';assert a.read_bytes()==b.read_bytes()
print(json.dumps({'all_six_file_hashes':True,'forward_reverse_patch_roundtrip':True,'source_and_installed_iqdbc_match':True}))
