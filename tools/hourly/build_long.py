import gzip, json, glob, numpy as np, os
LCS={'off':0,'pid':1,'stopping':2,'starting':3}
LPS={'cruise':0,'lead':1,'e2e':2,'blend':3}
LPER={'relaxed':0,'standard':1,'aggressive':2}
cols = ['t','v','a','acc','lon','en','cen','gas','brk','ss','curv','ala','dla','tq','tqo','p','i','f','out','err','act','prs','ang','rate','sat','dtq','yaw','lat',
        'l1s','ldr','lvr','lvl','lak','lmp','lp_at','sstop','hlead','lps_i','lcs_i','cc_at','mprob','mx','lper_i']
rows = []; routes = []
for fpath in sorted(glob.glob('/home/ubuntu/tucson/drives/export/*.jsonl.gz')):
    seg = os.path.basename(fpath).replace('.jsonl.gz','')
    route, segn = seg.rsplit('--',1)
    rid = int(route.split('--')[0],16)
    with gzip.open(fpath,'rt') as g:
        first = True
        for line in g:
            if first: first=False; continue
            r = json.loads(line)
            if 'v' not in r or 'acc' not in r: continue
            r['lps_i']=LPS.get(r.get('lps'),-1); r['lcs_i']=LCS.get(r.get('lcs'),-1); r['lper_i']=LPER.get(r.get('lper'),-1)
            rows.append([rid, int(segn)] + [float(r.get(c,0) if r.get(c) is not None else 0) for c in cols])
arr = np.array(rows, dtype=np.float32)
np.save('/home/ubuntu/tucson/drives/all_frames.npy', arr)
json.dump(['rid','seg']+cols, open('/home/ubuntu/tucson/drives/all_frames_cols.json','w'))
print(arr.shape)
