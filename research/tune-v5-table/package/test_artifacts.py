from pathlib import Path
import tempfile,subprocess,hashlib,json,shutil
p=Path(__file__).resolve().parent;m=json.loads((p/'manifest.json').read_text())
with tempfile.TemporaryDirectory(prefix='iq-tune-patch-roundtrip-') as t:
 r=Path(t)
 for e in m['files']:
  rel=e['path']
  for sub,key in [('candidate','candidate_sha256'),('rollback','original_sha256')]:
   f=p/sub/rel;assert hashlib.sha256(f.read_bytes()).hexdigest()==e[key]
  if rel.endswith(('.py','.cc','.toml')):
   f=r/rel;f.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p/'rollback'/rel,f)
 subprocess.run(['git','apply','--check',str(p/'forward.patch')],cwd=r,check=True)
 subprocess.run(['git','apply',str(p/'forward.patch')],cwd=r,check=True)
 for e in m['files']:
  if (r/e['path']).is_file():assert hashlib.sha256((r/e['path']).read_bytes()).hexdigest()==e['candidate_sha256']
 subprocess.run(['git','apply',str(p/'reverse.patch')],cwd=r,check=True)
 for e in m['files']:
  if (r/e['path']).is_file():assert hashlib.sha256((r/e['path']).read_bytes()).hexdigest()==e['original_sha256']
 for e in m['files']:
  for sub in ['candidate','rollback']:
   f=p/sub/e['path']
   if f.suffix=='.py':compile(f.read_bytes(),str(f),'exec')
print(json.dumps({'all_three_file_hashes':True,'forward_reverse_patch_roundtrip':True,'candidate_and_rollback_py_compile':True}))
