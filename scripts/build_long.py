import gzip, json, glob, numpy as np, os
cols = ['t','v','a','acc','lon','en','cen','gas','brk','ss','curv','ala','dla','tq','tqo','p','i','f','out','err','act','prs','ang','rate','sat','dtq','yaw','lat']
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
            rows.append([rid, int(segn)] + [float(r.get(c,0) or 0) for c in cols])
arr = np.array(rows, dtype=np.float32)
np.save('/home/ubuntu/tucson/drives/all_frames.npy', arr)
json.dump(['rid','seg']+cols, open('/home/ubuntu/tucson/drives/all_frames_cols.json','w'))
print(arr.shape)
