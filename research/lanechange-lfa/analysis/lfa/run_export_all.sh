#!/bin/bash
# export all post-install segs on device in chunks, then pull
cd /home/ubuntu/tucson/analysis/lfa
python3 - <<'PY'
import sys; sys.path.insert(0,'/home/ubuntu/tucson/hourly')
import refresh, subprocess, os
segs=open('post_segs.txt').read().split()
for i in range(0,len(segs),8):
    ch=segs[i:i+8]
    r=refresh.comma(f"cd /data/openpilot && PYTHONPATH={refresh.PPATH} {refresh.VENV} /data/tucson_stage/export_can_lfa.py "+' '.join(ch),timeout=900)
    print(r.stdout.strip()[-600:], r.stderr.strip()[-300:], flush=True)
for s in segs:
    dst=f'export/{s}.jsonl.gz'
    if os.path.exists(dst) and os.path.getsize(dst)>100: continue
    p=subprocess.run(f"ssh -o ConnectTimeout=10 mac 'ssh -o ConnectTimeout=20 comma \"cat /data/tucson-lfa-export/{s}.jsonl.gz\"' > {dst}",shell=True,capture_output=True,timeout=120)
    if p.returncode!=0 or os.path.getsize(dst)<100:
        os.path.exists(dst) and os.remove(dst); print('pull failed',s,flush=True)
print('DONE',flush=True)
PY
