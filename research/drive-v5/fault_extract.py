#!/usr/bin/env python3
"""Extract engage-failure evidence from rlogs on device. Usage: fault_extract.py <seg_dir>..."""
import sys, json
from iqpilot.tools.lib.logreader import LogReader

def g(o, k, d=None):
    try: return getattr(o, k)
    except Exception: return d

out = []
for seg in sys.argv[1:]:
    rec = {'seg': seg.split('/')[-1], 'events': [], 'en_trans': [], 'faults': [],
           'panda': [], 'dev': [], 'logs': [], 'model': []}
    prev_en = None
    try:
        for ev in LogReader(f'{seg}/rlog.zst'):
            w = ev.which(); t = ev.logMonoTime
            if w == 'onroadEvents':
                for e in ev.onroadEvents:
                    rec['events'].append({'t': t, 'name': str(g(e,'name',str(e)))})
            elif w == 'selfdriveState':
                en = bool(g(ev.selfdriveState,'enabled',False))
                if en != prev_en:
                    rec['en_trans'].append({'t': t, 'en': en,
                        'state': str(g(ev.selfdriveState,'state',''))})
                prev_en = en
            elif w == 'carState':
                cs = ev.carState
                sft = g(cs,'steerFaultTemporary'); sfp = g(cs,'steerFaultPermanent')
                cv = g(cs,'canValid'); ct = g(cs,'canTimeout')
                if sft or sfp or (cv is not None and not cv) or ct:
                    rec['faults'].append({'t':t,'sft':sft,'sfp':sfp,'canValid':cv,'canTimeout':ct,
                        'cruise':str(g(cs,'cruiseState',''))})
            elif w == 'pandaState':
                ps = ev.pandaState
                rec['panda'].append({'t':t,'allowed':g(ps,'controlsAllowed'),
                    'ign':g(ps,'ignitionLine'), 'sm':str(g(ps,'safetyModel','')),
                    'faults':str(g(ps,'faults','')), 'rx':g(ps,'rxErrors'), 'tx':g(ps,'txErrors'),
                    'canRx':g(ps,'canRxErrs'), 'canSend':g(ps,'canSendErrs')})
            elif w == 'deviceState':
                ds = ev.deviceState
                rec['dev'].append({'t':t,'free':g(ds,'freeSpacePercent'),
                    'therm':str(g(ds,'thermalStatus','')),'cpu':g(ds,'cpuTempC'),
                    'mem':g(ds,'memoryUsagePercent')})
            elif w in ('errorLogMessage','logMessage'):
                s = str(g(getattr(ev,w),'msg',g(getattr(ev,w),'message','')))
                if 'ERROR' in s.upper() or 'error' in s[:200].lower():
                    rec['logs'].append({'t':t,'svc':w,'msg':s[:300]})
            elif w == 'modelV2':
                m = ev.modelV2
                rec['model'].append({'t':t,'frame':g(m,'frameId'),
                    'exec':g(m,'modelExecutionTime'),'dropped':g(m,'frameDropPerc')})
    except Exception as e:
        rec['error'] = str(e)
    rec['panda_n'] = len(rec['panda']); rec['dev_n'] = len(rec['dev'])
    out.append(rec)
print(json.dumps(out, default=str))
