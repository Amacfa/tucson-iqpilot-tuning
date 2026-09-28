import gzip,json,os,collections,numpy as np,sys
EXP='/home/ubuntu/tucson/drives/export'
def load(f):
    with gzip.open(f'{EXP}/{f}','rt') as g: json.loads(g.readline()); return [json.loads(l) for l in g]
def band(x,dt,lo=0.5,hi=3.0):
    x=x-x.mean(); n=len(x); X=np.fft.rfft(x*np.hanning(n)); fr=np.fft.rfftfreq(n,dt); p=np.abs(X)**2
    tot=p[1:].sum(); b=p[(fr>=lo)&(fr<=hi)].sum()
    return (b/tot if tot>0 else 0), np.sqrt(2*b)/n*2  # frac, ~band amplitude
groups=collections.defaultdict(list)
for fn in sorted(os.listdir(EXP)):
    r=fn.split('--')[0]; n=int(r,16)
    g='baseline' if n<0x24 else ('v1_24' if n==0x24 else 'v2_'+r[-2:])
    groups[g].append(fn)
W=3.0
res={}
for g,fns in groups.items():
    hrs=collections.Counter(); ep=collections.Counter(); worst=[]
    for fn in fns:
        rows=load(fn)
        t=np.array([r['t'] for r in rows]); v=np.array([r.get('v') or 0 for r in rows]); ala=np.array([r.get('ala') or 0 for r in rows]); dla=np.array([r.get('dla') or 0 for r in rows])
        ok=np.array([bool(r.get('lat')) and not r.get('prs') for r in rows])
        i=0; n=len(rows); dt=np.median(np.diff(t))
        step=int(W/dt)
        while i+step<n:
            seg=slice(i,i+step)
            if ok[seg].all() and v[seg].mean()>=5:
                b='5-10' if v[seg].mean()<10 else '10-15' if v[seg].mean()<15 else '15-20' if v[seg].mean()<20 else '20+'
                hrs[b]+=W/3600
                fa,amp=band(ala[seg],dt); fd,_=band(dla[seg],dt)
                err=ala[seg]-dla[seg]; fe,ampe=band(err,dt)
                if fe>0.6 and ampe>0.4:
                    ep[b]+=1; worst.append((round(ampe,2),fn,round(t[i],1),round(v[seg].mean(),1)))
            i+=step
    res[g]=dict(active_hr={k:round(x,3) for k,x in hrs.items()}, episodes=dict(ep), per_hr={k:round(ep[k]/hrs[k],1) for k in hrs if hrs[k]>0})
    print(g,json.dumps(res[g]))
    print('  worst',sorted(worst,reverse=True)[:6])
json.dump(res,open('/home/ubuntu/tucson/analysis/wobble/osc_episodes.json','w'),indent=1)
