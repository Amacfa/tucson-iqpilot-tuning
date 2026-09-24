"""Replay route23 CAN inputs + in-memory generated LFA through the unchanged extracted C policy.

Source policy only (hyundai_canfd.h/hyundai_common.h/lateral.h/aol.h identical on device);
not flashed firmware, physical CAN delivery or EPS acceptance.
"""
import ctypes as C, gzip, hashlib, json, sys
from pathlib import Path

R = Path(__file__).resolve().parent
lib = C.CDLL(str(R / 'harness_linux.so'))
lib.test_reset.argtypes = [C.c_bool, C.c_bool, C.c_bool]
lib.test_tx.argtypes = [C.c_int, C.c_int, C.c_uint32]
lib.test_rx.argtypes = [C.c_int, C.c_int, C.c_int]
MAIN2_S, SETREL_S = 78.355, 114.685  # native MAIN toggle (off) and first later SET release


def main(result_path, out_path):
  wrapper = json.loads(Path(result_path).read_text())
  assert wrapper['protected_state_unchanged'] and not wrapper['error']
  result = wrapper['result']
  meta = json.loads((R / 'route23-metadata-pubtime.json').read_text())
  fixture = R / 'route23-fixture-pubtime.jsonl.gz'
  assert hashlib.sha256(fixture.read_bytes()).hexdigest() == meta['fixture_sha256'] == result['fixture_sha256']
  origin = meta['origin_ns']; events = []
  for line in gzip.open(fixture, 'rt'):
    row = json.loads(line)
    if row[0] != 'can': continue
    t = (row[1] - origin) * 1e-9
    for address, h, bus in row[2]:
      if bus != 0: continue
      w = int.from_bytes(bytes.fromhex(h), 'little')
      if address == 0x1aa: events.append((t, 1, (w >> 36) & 7, (w >> 34) & 1))
      elif address == 0x175: events.append((t, 2, (w >> 81) & 1, 0))
      elif address == 0xea: events.append((t, 3, ((w >> 80) & 8191) - 4095, 0))
  out = {}
  for key in ('original', 'candidate'):
    ev = list(events)
    for f in result['runs'][key]['generated_lfa']:
      if f['bus'] == 0: ev.append((f['t_s'], 4, f['torque'], f['request']))
    ev.sort(key=lambda x: (x[0], x[1]))
    lib.test_reset(False, False, True); rows = []
    for t, kind, value, mainbit in ev:
      if kind != 4: lib.test_rx(kind, value, mainbit); continue
      st = lib.test_state()
      accepted = not bool(lib.test_tx(value, mainbit, round(t * 1e6) & 0xffffffff))
      rows.append(dict(t=round(t, 4), torque=value, request=mainbit, accepted=accepted,
                       native_controls=bool(st & 1), native_main=bool(st & 2), native_aol=bool(st & 4)))
    window = [r for r in rows if MAIN2_S <= r['t'] < SETREL_S]
    rejected = [r for r in rows if not r['accepted']]
    def spans(rs):
      s = []; cur = None
      for r in rs:
        if cur and r['t'] - cur[1] < 0.2: cur[1] = r['t']; cur[2] += 1
        else:
          cur = [r['t'], r['t'], 1]; s.append(cur)
      return s
    out[key] = {'frames': len(rows), 'rejected': len(rejected), 'rejected_spans': spans(rejected),
      'active_frames': sum(r['torque'] != 0 or r['request'] != 0 for r in rows),
      'window_frames': len(window), 'window_active': sum(r['torque'] != 0 or r['request'] != 0 for r in window),
      'window_rejected': sum(not r['accepted'] for r in window),
      'accepted_active_frames': sum(r['accepted'] and (r['torque'] != 0 or r['request'] != 0) for r in rows),
      'first_native_controls_s': next((r['t'] for r in rows if r['native_controls']), None),
      'native_main_spans': spans([r for r in rows if r['native_main']]),
      'native_aol_spans': spans([r for r in rows if r['native_aol']]),
      'first_active_s': next((r['t'] for r in rows if r['torque'] != 0 or r['request'] != 0), None)}
  # Baseline must reproduce the rejected active retry loop; candidate must send nothing active in the window
  # and nothing anywhere that the unchanged policy rejects.
  assert out['original']['window_active'] > 0 and out['original']['window_rejected'] > 0
  assert out['candidate']['window_frames'] > 3000 and out['candidate']['window_active'] == 0
  assert out['candidate']['rejected'] == 0
  assert out['candidate']['accepted_active_frames'] > 0  # ordinary engagement after the fresh SET release still works
  # Fidelity: original in-memory LFA vs the LFA the device actually published on route23 (nearest within 15 ms).
  rec = sorted((f['t_s'], f['torque'], f['request']) for f in result['recorded_sent_lfa'] if f['bus'] == 0)
  import bisect
  rt = [r[0] for r in rec]; same = compared = 0
  for f in result['runs']['original']['generated_lfa']:
    if f['bus'] != 0 or f['t_s'] < 10: continue
    i = bisect.bisect_left(rt, f['t_s']); cands = [rec[j] for j in (i - 1, i) if 0 <= j < len(rec)]
    if not cands: continue
    r = min(cands, key=lambda c: abs(c[0] - f['t_s']))
    if abs(r[0] - f['t_s']) > 0.015: continue
    compared += 1; same += (abs(r[1] - f['torque']) <= 2 and r[2] == f['request'])
  out['original_vs_recorded_lfa'] = {'compared': compared, 'matching_torque_within2_and_request': same,
                                     'ratio': round(same / max(compared, 1), 4), 'recorded_frames': len(rec)}
  assert out['original_vs_recorded_lfa']['ratio'] > 0.95
  out['fixture_sha256'] = meta['fixture_sha256']
  out['harness_c_sha256'] = '1d01c98a6420517c0837969da670e4e378180dbe290a26c1de81eecd4d469bef'
  out['limitations'] = ['Extracted C source policy compiled on Linux, not flashed image, USB/CAN transport or EPS.',
    'Native state initialised main=false/aol=false/controls=false at route start; all later transitions come from replayed RX.',
    'Recorded EPS fault stays frozen input; dashboard warning disappearance cannot be inferred from this replay.']
  Path(out_path).write_text(json.dumps(out, indent=1) + '\n')
  print(json.dumps({k: {x: v for x, v in d.items() if not isinstance(v, list)} for k, d in out.items() if k in ('original', 'candidate')}, indent=1))
  print('fidelity', out['original_vs_recorded_lfa'])
  print('original rejected spans', out['original']['rejected_spans'][:25])
  print('native main spans', out['original']['native_main_spans'], 'aol', out['original']['native_aol_spans'])


if __name__ == '__main__':
  main(sys.argv[1], sys.argv[2])
