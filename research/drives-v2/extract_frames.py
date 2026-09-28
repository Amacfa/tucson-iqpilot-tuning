import gzip,json,os,sys,numpy as np
EXP='/home/ubuntu/tucson/drives/export'
prefixes=sys.argv[2:]; out=sys.argv[1]
keys=dict(t='t',vEgo='v',aEgo='a',dla='dla',ala='ala',ang='ang',rate='rate',dtq='dtq',dtqe='dtqe',prs='prs',tq='tq',tqo='tqo',p='p',i='i',f='f',out='out',act='lat',err='err',sat='sat',yaw='yaw',laf='lp_at')
cols={k:[] for k in keys}; segs=[]
for fn in sorted(os.listdir(EXP)):
    if not any(fn.startswith(p) for p in prefixes): continue
    with gzip.open(f'{EXP}/{fn}','rt') as g:
        json.loads(g.readline())
        for l in g:
            r=json.loads(l)
            if not r.get('lat'): continue
            for k,src in keys.items(): cols[k].append(r.get(src) or 0)
            segs.append(fn[:-9])
arr={k:np.array(v,float) for k,v in cols.items()}; arr['seg']=np.array(segs)
np.savez(out,**arr); print(out,len(segs))
