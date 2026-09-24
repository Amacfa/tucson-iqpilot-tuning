"""Device-side, read-only export of a publication-ordered replay fixture for route23.

Reads hash-verified rlog segments from /data/media/0/realdata, writes only under
/tmp. Nothing is published, no Params are touched, no CAN is sent.
Rows: ['can', t, [[addr,hex,bus],...]]            CAN input batch
      ['sent', t, [[addr,hex,bus],...]]           recorded sendcan LFA(298) only (evidence, not input)
      ['tick', t, carState, recent, recent_t]     CarState publication tick with frozen latest messages
Frozen 'recent' kinds include pandaStates so the candidate card/CarState arming sync can be replayed.
"""
import sys, os, json, gzip, hashlib, io
sys.path.insert(0, '/data/openpilot')
os.environ.setdefault('PYTHONDONTWRITEBYTECODE', '1')
import zstandard
from iqpilot.cereal import log as schema

ROUTE = '00000023--<redacted>'
SEGMENTS = [0, 1, 2]
UNTIL_S = 125.0
BASE = '/data/media/0/realdata'
OUT_FIXTURE = '/tmp/route23-fixture-pubtime.jsonl.gz'
OUT_META = '/tmp/route23-metadata-pubtime.json'
RECENT = ('carControl', 'iqState', 'selfdriveState', 'onroadEvents', 'pandaStates')

def clean(v):
  if isinstance(v, bytes): return {'__bytes__': v.hex()}
  if isinstance(v, dict): return {k: clean(x) for k, x in v.items()}
  if isinstance(v, (list, tuple)): return [clean(x) for x in v]
  return v

def events(data):
  # Full segments decode completely; a truncated tail (still-open writer) stops iteration.
  try:
    for e in schema.Event.read_multiple_bytes(data, traversal_limit_in_words=2**30):
      yield e
  except Exception as exc:  # noqa: BLE001 - truncated final frame only
    print('decode stopped:', repr(exc)[:200], file=sys.stderr)

def main():
  meta = {'route': ROUTE, 'segments': [], 'until_s': UNTIL_S,
          'note': 'CAN envelope times and CarState publication ticks; not exact acquisition/callback ordering.',
          'recent_kinds': list(RECENT)}
  origin = None; counts = {}; records = []
  for seg in SEGMENTS:
    p = f'{BASE}/{ROUTE}--{seg}/rlog.zst'
    raw = open(p, 'rb').read()
    meta['segments'].append({'path': p, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw)) as f: data = f.read()
    del raw
    for e in events(data):
      t = int(e.logMonoTime); k = e.which()
      if origin is None and k == 'initData':
        origin = t
        d = e.initData.to_dict(); meta['params'] = clean(d.get('params', {}))
        meta['source'] = {x: d.get(x) for x in ('gitCommit', 'gitBranch', 'version', 'dirty')}
      if origin is None: continue
      if t > origin + int(UNTIL_S * 1e9): continue
      if k in ('carParams', 'iqCarParams') and k not in meta:
        meta[k] = clean(getattr(e, k).to_dict())
      if k in RECENT:
        value = getattr(e, k)
        records.append((t, len(records), ['recent', t, k,
          clean(value.to_dict() if hasattr(value, 'to_dict') else [x.to_dict() for x in value])]))
      elif k == 'can':
        records.append((t, len(records), ['can', t, [[int(c.address), bytes(c.dat).hex(), int(c.src)] for c in e.can]]))
      elif k == 'sendcan':
        lfa = [[int(c.address), bytes(c.dat).hex(), int(c.src)] for c in e.sendcan if int(c.address) == 298]
        if lfa: records.append((t, len(records), ['sent', t, lfa]))
      elif k == 'carState':
        records.append((t, len(records), ['tick', t, clean(e.carState.to_dict())]))
      else:
        continue
      counts[k] = counts.get(k, 0) + 1
    del data
  assert origin is not None, 'initData not found'
  meta['origin_ns'] = origin
  records.sort(key=lambda x: (x[0], x[1]))
  recent = {}; recent_t = {}; reordered = 0; last_ordinal = -1
  with gzip.open(OUT_FIXTURE, 'wt', compresslevel=6) as out:
    for t, ordinal, row in records:
      if ordinal < last_ordinal: reordered += 1
      last_ordinal = ordinal
      if row[0] == 'recent':
        recent[row[2]] = row[3]; recent_t[row[2]] = t; continue
      if row[0] == 'tick':
        assert all(v <= t for v in recent_t.values())
        row = row + [recent.copy(), recent_t.copy()]
      out.write(json.dumps(row, separators=(',', ':')) + '\n')
  meta['counts'] = counts
  meta['file_order_reversals_repaired'] = reordered
  meta['ordering'] = ('Stable global event-publication-time ordering. Each CAN and frozen-state envelope '
                      'timestamp is <= the consuming CarState publication tick.')
  meta['fixture_sha256'] = hashlib.sha256(open(OUT_FIXTURE, 'rb').read()).hexdigest()
  json.dump(meta, open(OUT_META, 'w'))
  print(json.dumps({'origin_ns': origin, 'counts': counts, 'reordered': reordered,
                    'fixture_sha256': meta['fixture_sha256'], 'bytes': os.path.getsize(OUT_FIXTURE),
                    'source': meta['source'], 'has_carParams': 'carParams' in meta, 'has_iqCarParams': 'iqCarParams' in meta}))

if __name__ == '__main__':
  main()
