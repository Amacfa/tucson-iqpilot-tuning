"""Meaningful package fault injection: checksum refusal and partial-write recovery."""
from pathlib import Path
import importlib.util,tempfile,json,hashlib
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('manage',H/'manage.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
with tempfile.TemporaryDirectory(prefix='iq-package-transaction-') as td:
 root=Path(td)/'root';pkg=Path(td)/'package';root.mkdir();pkg.mkdir();m.HERE=pkg
 entries=[]
 for name,old,new in [('a.py',b'x=1\n',b'x=2\n'),('b.py',b'y=3\n',b'y=4\n'),('daemon',b'old-binary',b'new-binary')]:
  (root/name).write_bytes(old)
  for sub,data in [('candidate',new),('rollback',old)]:
   (pkg/sub).mkdir(exist_ok=True);(pkg/sub/name).write_bytes(data)
  entries.append(dict(path=name,original_sha256=hashlib.sha256(old).hexdigest(),candidate_sha256=hashlib.sha256(new).hexdigest(),mode=0o644))
 manifest={'files':entries};(pkg/'manifest.json').write_text(json.dumps(manifest))
 m.checked_files(root,manifest,'apply')
 saved_replace=m.os.replace;calls=[0]
 def fail_second(a,b):
  calls[0]+=1
  if calls[0]==2:raise OSError('injected second-file replacement failure')
  return saved_replace(a,b)
 m.os.replace=fail_second
 try:
  try:m.transaction(root,manifest,'apply',Path(td)/'failed-backup')
  except OSError:pass
  else:raise AssertionError('injected write failure was ignored')
 finally:m.os.replace=saved_replace
 m.checked_files(root,manifest,'apply')
 assert not list(root.glob('.iq-warning-*'))
 original_write=Path.write_text
 def fail_receipt(path,*a,**kw):
  if path.name=='receipt.json':raise OSError('injected receipt write failure')
  return original_write(path,*a,**kw)
 Path.write_text=fail_receipt
 try:
  try:m.transaction(root,manifest,'apply',Path(td)/'receipt-failure-backup')
  except OSError:pass
  else:raise AssertionError('receipt failure ignored')
 finally:Path.write_text=original_write
 m.checked_files(root,manifest,'apply')
 m.transaction(root,manifest,'apply',Path(td)/'apply-backup');m.checked_files(root,manifest,'rollback')
 m.transaction(root,manifest,'rollback',Path(td)/'rollback-backup');m.checked_files(root,manifest,'apply')
 # A power loss can leave an exact mixture; rollback must restore it safely.
 (root/'a.py').write_bytes((pkg/'candidate/a.py').read_bytes())
 m.checked_files(root,manifest,'rollback')
 m.transaction(root,manifest,'rollback',Path(td)/'mixed-rollback-backup');m.checked_files(root,manifest,'apply')
 (root/'a.py').write_bytes(b'new user work\n')
 try:m.checked_files(root,manifest,'apply')
 except RuntimeError:pass
 else:raise AssertionError('unrelated edits would be overwritten')
 import subprocess,sys
 code="import importlib.util; s=importlib.util.spec_from_file_location('guarded',"+repr(str(H/'manage.py'))+"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.require(False,'optimized refusal')"
 child=subprocess.run([sys.executable,'-O','-c',code],capture_output=True,text=True)
 assert child.returncode!=0 and 'optimized refusal' in child.stderr
 print(json.dumps({'apply_rollback_exact':True,'partial_write_failure_restores_originals':True,'temporary_files_removed':True,'unrelated_edit_refused':True,'mixed_original_candidate_rollback':True,'receipt_failure_restores_originals':True,'guards_survive_python_optimization':True}))
