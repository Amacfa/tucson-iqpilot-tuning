"""Compare stock MDPS (0xea) frames from the car (bus 0) with what the camera sees on bus 2
(forwarded copies in 'can' and IQ's relayed copies in 'sendcan'). Byte-level diff, per segment."""
import gzip, json, glob, sys
from collections import Counter

files = sorted(glob.glob('/home/ubuntu/tucson/analysis/lfa/export/*.jsonl.gz'))
if len(sys.argv) > 1: files = [f for f in files if any(a in f for a in sys.argv[1:])]
tot = Counter(); bytediff = Counter(); examples = []
for f in files:
  last0 = None; can2 = 0; send2 = 0; n0 = 0
  for l in gzip.open(f, 'rt'):
    r = json.loads(l)
    if r.get('a') != 234: continue
    if r['k'] == 'can' and r['b'] == 0:
      last0 = bytes.fromhex(r['d']); n0 += 1
    elif r['k'] == 'can' and r['b'] == 2:
      can2 += 1
      if last0 is not None:
        d = bytes.fromhex(r['d'])
        if d != last0: tot['can2_differs_from_last_bus0'] += 1
    elif r['k'] == 'sendcan':
      send2 += 1
      if last0 is not None:
        d = bytes.fromhex(r['d'])
        if d == last0: tot['sendcan_identical'] += 1
        else:
          tot['sendcan_differs'] += 1
          for i, (x, y) in enumerate(zip(d, last0)):
            if x != y: bytediff[i] += 1
          if len(examples) < 6: examples.append((f[-30:-9], r['t'], last0.hex(), d.hex()))
  tot['bus0'] += n0; tot['can_bus2'] += can2; tot['sendcan_bus2'] += send2
print(dict(tot))
print('bytes that differ (index: count):', dict(sorted(bytediff.items())))
for e in examples: print(e)
