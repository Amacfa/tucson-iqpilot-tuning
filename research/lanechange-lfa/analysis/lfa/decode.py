"""Decode the on-device LFA/CAN export with the Hyundai CAN-FD DBC (cantools)."""
import gzip, json, os
import cantools

DBC = '/home/ubuntu/tucson/analysis/tucson-recurring-warnings-20260923/today-identity-review/current-hyundai_canfd_generated.dbc'
EXPORT = '/home/ubuntu/tucson/analysis/lfa/export'
db = cantools.database.load_file(DBC, strict=False)
MSG = {m.frame_id: m for m in db.messages}
for _m in MSG.values():
  _need = max(_m.length, max(((s.start + s.length - 1) // 8 + 1) for s in _m.signals))
  if _need > _m.length:
    _m.length = _need
    _m.refresh()


def decode(addr, hexdat):
  m = MSG.get(addr)
  if m is None:
    return None
  dat = bytes.fromhex(hexdat)
  try:
    return m.decode(dat[:m.length].ljust(m.length, b'\0'), decode_choices=False)
  except Exception:
    return None


def load(seg):
  with gzip.open(f'{EXPORT}/{seg}.jsonl.gz', 'rt') as g:
    for line in g:
      yield json.loads(line)


def segs():
  return sorted(f[:-9] for f in os.listdir(EXPORT) if f.endswith('.jsonl.gz'))
