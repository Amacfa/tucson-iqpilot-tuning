#!/usr/bin/env python3
"""Unit test for the LFA A/B variant bitmask in the candidate hyundaicanfd.py.

Loads the orig and candidate modules side by side, drives
create_steering_messages_camera_scc / create_lfahda_cluster through a real
DBC-driven packer (cantools + the generated hyundai_canfd DBC) and asserts the
per-bit behaviors. Stubbed: iqpilot.common.params (Params), iqpilot.cereal (log
namespace) — capnp is unavailable off-device; iqdbc itself is the real device
tree in ../pydeps.
"""
import copy
import enum
import importlib.util
import json
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
WORK = os.path.join(os.path.dirname(PKG), 'work')
PYDEPS = os.path.join(os.path.dirname(PKG), 'pydeps')
DBC = '/home/ubuntu/tucson/analysis/tucson-recurring-warnings-20260923/today-review/hyundai_canfd_generated.dbc'

# --- shims for python 3.10 / missing capnp -------------------------------
if not hasattr(enum, 'ReprEnum'):
  enum.ReprEnum = enum.Enum
if not hasattr(enum, 'StrEnum'):
  class StrEnum(str, enum.Enum):
    def __str__(self):
      return str(self.value)
  enum.StrEnum = StrEnum
if not hasattr(enum, 'EnumType'):
  enum.EnumType = type(enum.Enum)
import typing
if not hasattr(typing, 'dataclass_transform'):
  typing.dataclass_transform = lambda *a, **k: (lambda f: f)

sys.path.insert(0, PYDEPS)

# --- stub iqdbc.car package object (real __init__ imports capnp structs) ---
# submodules still load from the real device tree via __path__.
iqdbc = types.ModuleType('iqdbc'); iqdbc.__path__ = [os.path.join(PYDEPS, 'iqdbc')]
iqcar = types.ModuleType('iqdbc.car'); iqcar.__path__ = [os.path.join(PYDEPS, 'iqdbc', 'car')]


class CanBusBase:
  def __init__(self, CP, fingerprint=None):
    num = len(CP.safetyConfigs) if CP is not None else 1
    self.offset = 4 * (num - 1)


iqcar.CanBusBase = CanBusBase
sys.modules['iqdbc'] = iqdbc
sys.modules['iqdbc.car'] = iqcar

# iqdbc.car.hyundai.values pulls capnp-heavy modules; stub the two flag enums
# with the real device values (iqdbc/car/hyundai/values.py @3736edc).
iq_hy = types.ModuleType('iqdbc.car.hyundai'); iq_hy.__path__ = [os.path.join(PYDEPS, 'iqdbc', 'car', 'hyundai')]
iq_hyv = types.ModuleType('iqdbc.car.hyundai.values')


class HyundaiFlags(enum.IntFlag):
  CANFD_HDA2 = 1; CANFD_ALT_BUTTONS = 2; CANFD_ALT_GEARS = 4; CANFD_CAMERA_SCC = 8
  ALT_LIMITS = 16; ENABLE_BLINKERS = 32; CANFD_ALT_GEARS_2 = 64; SEND_LFA = 128
  USE_FCA = 256; CANFD_HDA2_ALT_STEERING = 512; HYBRID = 1024; EV = 2048
  MANDO_RADAR = 4096; CANFD = 8192; RADAR_SCC = 16384; CAMERA_SCC = 8
  CHECKSUM_CRC8 = 65536; CHECKSUM_6B = 131072; LEGACY = 262144
  UNSUPPORTED_LONGITUDINAL = 524288; CANFD_NO_RADAR_DISABLE = 1048576
  CLUSTER_GEARS = 2097152; TCU_GEARS = 4194304; MIN_STEER_32_MPH = 8388608
  ANGLE_CONTROL = 16777216; FCEV = 33554432; ALT_LIMITS_2 = 67108864
  CC_ONLY_CAR = 2147483648


class HyundaiExtFlags(enum.IntFlag):
  NAVI_CLUSTER = 4; HAS_LFAHDA = 16; CANFD_GEARS_NONE = 64; RADAR_GROUP1 = 128
  CANFD_GEARS_69 = 1024; RADAR_GROUP3 = 2048; CORNER_RADAR_OBJECTS_235 = 4096
  CORNER_RADAR_OBJECTS_180 = 8192; CORNER_RADAR_OBJECTS_430 = 16384
  RADAR_GROUP4 = 32768; EV_MODE_STATUS_230 = 65536


iq_hyv.HyundaiFlags = HyundaiFlags
iq_hyv.HyundaiExtFlags = HyundaiExtFlags
sys.modules['iqdbc.car.hyundai'] = iq_hy
sys.modules['iqdbc.car.hyundai.values'] = iq_hyv

# stub iqpilot.common.params + iqpilot.cereal (capnp not available locally)
iqpilot = types.ModuleType('iqpilot'); iqpilot.__path__ = []
iq_common = types.ModuleType('iqpilot.common'); iq_common.__path__ = []
iq_params = types.ModuleType('iqpilot.common.params')


class Params:
  def get(self, key, return_default=False):
    return None

  def get_int(self, key):
    return 0

  def get_bool(self, key):
    return False


iq_params.Params = Params
iq_cereal = types.ModuleType('iqpilot.cereal')
_log = types.SimpleNamespace()
for n in ('LaneChangeState', 'LaneChangeDirection', 'Desire'):
  setattr(_log, n, enum.IntEnum(n, {'_': 0}))
_log.warning = enum.IntEnum('warning', {'_': 0})
iq_cereal.log = _log
sys.modules.update({'iqpilot': iqpilot, 'iqpilot.common': iq_common,
                    'iqpilot.common.params': iq_params, 'iqpilot.cereal': iq_cereal})

import re  # noqa: E402


def parse_dbc(path):
  msgs = {}
  name = None
  sigs = []
  bo = re.compile(r'^BO_ (\d+) (\w+): (\d+)')
  sg = re.compile(r'^\s*SG_ (\w+)\s*\w*\s*:\s*(\d+)\|(\d+)@(\d)([+-])\s*\((-?[\d.e]+),(-?[\d.e]+)\)')
  for line in open(path):
    m = bo.match(line)
    if m:
      if name: msgs[name] = (fid, length, sigs)
      fid = int(m.group(1)) & 0x7FFFFFFF; name = m.group(2); length = int(m.group(3)); sigs = []
      continue
    m = sg.match(line)
    if m and name:
      sigs.append(dict(name=m.group(1), start=int(m.group(2)), length=int(m.group(3)),
                       order=int(m.group(4)), sign=(m.group(5) == '-'),
                       scale=float(m.group(6)), offset=float(m.group(7))))
  if name: msgs[name] = (fid, length, sigs)
  return msgs


def _motorola_bits(start, length):
  """Physical bit positions for a big-endian (@0) signal, MSB first."""
  bits = []
  byte, bit = divmod(start, 8)
  pos = byte * 8 + (7 - bit)  # sawtooth -> linear position of MSB
  for _ in range(length):
    bits.append(pos)
    if pos % 8 == 0:
      pos += 15
    else:
      pos -= 1
  return bits


class _Msg:
  def __init__(self, fid, length, sigs):
    self.frame_id = fid; self.length = length; self.signals = sigs
    self._names = {x['name'] for x in sigs}


class _Db:
  def __init__(self, msgs):
    self._m = msgs
    self._byid = {v[0]: (k,) + v[1:] for k, v in msgs.items()}

  def get_message_by_name(self, n):
    fid, length, sigs = self._m[n]
    return _Msg(fid, length, sigs)

  def get_message_by_frame_id(self, fid):
    n, length, sigs = self._byid[fid]
    return _Msg(fid, length, sigs)

  def decode_message(self, fid, data):
    msg = self.get_message_by_frame_id(fid)
    out = {}
    for s in msg.signals:
      if s['order'] == 1:
        val = 0
        for i in range(s['length']):
          pos = s['start'] + i
          if pos >= len(data) * 8:
            break
          val |= ((data[pos // 8] >> (pos % 8)) & 1) << i
      else:
        val = 0
        for pos in _motorola_bits(s['start'], s['length']):
          if pos >= len(data) * 8:
            val <<= 1
            continue
          val = (val << 1) | ((data[pos // 8] >> (pos % 8)) & 1)
      if s['sign'] and s['length'] > 1 and val >= (1 << (s['length'] - 1)):
        val -= 1 << s['length']
      out[s['name']] = val * s['scale'] + s['offset']
    return out


def _encode(msg, values):
  bits = 0
  for s in msg.signals:
    if s['name'] not in values:
      continue
    raw = int(round((values[s['name']] - s['offset']) / s['scale'])) if s['scale'] != 1 or s['offset'] else int(values[s['name']])
    if s['sign'] and raw < 0:
      raw += 1 << s['length']
    raw &= (1 << s['length']) - 1
    if s['order'] == 1:
      bits |= raw << s['start']
    else:
      for i, pos in enumerate(_motorola_bits(s['start'], s['length'])):
        bit = (raw >> (s['length'] - 1 - i)) & 1
        bits |= bit << pos
  return bits.to_bytes(msg.length, 'little')


def load_module(path, name):
  spec = importlib.util.spec_from_file_location(name, path)
  m = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(m)
  return m


ORIG = load_module(os.path.join(WORK, 'hyundaicanfd.orig.py'), 'hcfd_orig')
CAND = load_module(os.path.join(PKG, 'candidate/.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/hyundaicanfd.py'), 'hcfd_cand')


class Packer:
  """DBC-driven stand-in for CANPacker: deterministic encode/decode built
  directly from BO_/SG_ lines (the generated CAN-FD DBC is not cantools-strict
  compatible - it declares signals beyond the message length). Encode/decode are
  self-consistent; byte-level equivalence vs the on-device C++ packer is NOT
  verified off-device."""

  def __init__(self, dbc):
    self.db = _Db(parse_dbc(dbc))

  def make_can_msg(self, name_or_id, bus, values, rx_counter=None):
    msg = self.db.get_message_by_name(name_or_id) if isinstance(name_or_id, str) \
      else self.db.get_message_by_frame_id(name_or_id)
    v = dict(values)
    if 'COUNTER' in msg._names:
      v['COUNTER'] = rx_counter if rx_counter is not None else v.get('COUNTER', 0)
    if 'CHECKSUM' in msg._names:
      v['CHECKSUM'] = 0
    return (msg.frame_id, _encode(msg, v), bus)

  def decode(self, frame_id, data):
    return self.db.decode_message(frame_id, data)


class CS:
  pass


def mk_cs():
  cs = CS()
  cs.mdps = {'CHECKSUM': 1, 'COUNTER': 7, 'NEW_SIGNAL_1': 2, 'NEW_SIGNAL_2': 3,
             'LKA_ACTIVE': 0, 'LKA_FAULT': 0, 'STEERING_OUT_TORQUE': 12.5,
             'STEERING_COL_TORQUE': 10, 'STEERING_ANGLE': -15.0, 'STEERING_ANGLE_2': -15.0}
  cs.lfa = {'COUNTER': 5, 'CHECKSUM': 0, 'LKA_MODE': 1, 'LKA_ACTIVE': 0,
            'LKA_WARNING': 0, 'LKA_ICON': 0, 'TORQUE_REQUEST': 0, 'STEER_REQ': 0,
            'NEW_SIGNAL_1': 8, 'LKAS_ANGLE_ACTIVE': 0, 'HAS_LANE_SAFETY': 1,
            'LKAS_ANGLE_CMD': 0, 'LKAS_ANGLE_MAX_TORQUE': 0, 'DampingGain': 100}
  cs.steer_touch_2af = {'CHECKSUM_': 0, 'COUNTER_': 3, 'TOUCH_DETECT': 0, 'TOUCH1': 0, 'TOUCH2': 0}
  cs.lfa_alt = None
  cs.adrv_0x161 = None
  cs.cam_0x362 = None
  cs.lfahda_cluster = {'COUNTER': 1, 'CHECKSUM': 0, 'HDA_OptUsmSta': 1,
                       'HDA_CntrlModSta': 1, 'HDA_InfoPUDis': 0, 'HDA_AutoSetSpdSta': 0,
                       'HDA_AutoSetSpdUpdtSta': 0, 'HDA_AutoSetSpdVal': 0,
                       'HDA_LFA_SymSta': 1, 'HDA_LFA_WrnSnd': 0, 'HDA_InfoPUDis1': 0,
                       'HDA_TDMRMDclReq': 0}
  return cs


PACKER = Packer(DBC)


class CAN:
  ECAN = 0
  ACAN = 1
  CAM = 2


class CP:
  flags = 0


class CC:
  enabled = True
  latActive = True
  value = 0


def set_variant(mod, val, tmpdir):
  path = os.path.join(tmpdir, 'lfa_ab')
  if val is None:
    if os.path.exists(path):
      os.remove(path)
  else:
    with open(path, 'w') as f:
      f.write(str(val))
  mod.LFA_AB_FILE = path
  mod._lfa_ab = None


def steer_msgs(mod, frame, lat_active=True, apply_steer=0, apply_angle=0, cs=None):
  return mod.create_steering_messages_camera_scc(frame, PACKER, CP, CAN, CC, lat_active,
                                                 apply_steer, cs or mk_cs(), apply_angle,
                                                 300, False)


def by_name(packer, msgs, name):
  fid = packer.db.get_message_by_name(name).frame_id
  return [m for m in msgs if m[0] == fid]


def main():
  tmpdir = tempfile.mkdtemp()
  res = {}

  # variant 0 == orig byte-for-byte on all messages
  ident = True
  for frame in (0, 5, 10, 500):
    for la in (True, False):
      set_variant(CAND, 0, tmpdir)
      a = steer_msgs(CAND, frame, lat_active=la, apply_steer=120)
      b = steer_msgs(ORIG, frame, lat_active=la, apply_steer=120)
      if a != b:
        ident = False
  res['variant0_identical_to_orig'] = ident

  # missing/invalid file -> variant 0
  set_variant(CAND, None, tmpdir)
  assert CAND.lfa_ab_variant() == 0
  with open(os.path.join(tmpdir, 'lfa_ab'), 'w') as f:
    f.write('garbage')
  CAND._lfa_ab = None
  assert CAND.lfa_ab_variant() == 0
  res['missing_or_invalid_variant_defaults_0'] = True

  # bit 1: camera LFA fields pass through, control fields overridden
  set_variant(CAND, 1, tmpdir)
  msgs = steer_msgs(CAND, 0, lat_active=True, apply_steer=111)
  d = PACKER.decode(*by_name(PACKER, msgs, 'LFA')[0][:2])
  res['bit1_lfa_passthrough'] = (d['LKA_MODE'] == 1 and d['HAS_LANE_SAFETY'] == 1 and
                               d['NEW_SIGNAL_1'] == 8 and d['STEER_REQ'] == 1 and
                               d['TORQUE_REQUEST'] == 111 and d['LKA_ICON'] == 2)
  res['bit1_lfa_len_same_as_v0'] = (len(by_name(PACKER, msgs, 'LFA')[0][1]) ==
                                  len(by_name(PACKER, steer_msgs(CAND, 0, True, 111), 'LFA')[0][1]))

  # bit 2: MDPS relayed unmodified (frame 5 is inside spoof window in v0)
  set_variant(CAND, 2, tmpdir)
  msgs = steer_msgs(CAND, 5, lat_active=True, apply_steer=50)
  d = PACKER.decode(*by_name(PACKER, msgs, 'MDPS')[0][:2])
  exp = copy.copy(mk_cs().mdps)
  res['bit2_mdps_unmodified'] = all(d[k] == v for k, v in exp.items()
                                  if k in d and k not in ('CHECKSUM', 'COUNTER'))
  # with CS.lfa STEER_REQ=1, LKA_ACTIVE must NOT be rewritten to 1
  cs2 = mk_cs(); cs2.lfa['STEER_REQ'] = 1
  msgs2 = steer_msgs(CAND, 7, lat_active=False, apply_steer=0, cs=cs2)
  d2 = PACKER.decode(*by_name(PACKER, msgs2, 'MDPS')[0][:2])
  res['bit2_lka_active_not_rewritten'] = (d2['LKA_ACTIVE'] == mk_cs().mdps['LKA_ACTIVE'])
  msgs3 = steer_msgs(CAND, 10, lat_active=False, apply_steer=0)
  d3 = PACKER.decode(*by_name(PACKER, msgs3, 'STEER_TOUCH_2AF')[0][:2])
  res['bit2_touch_unmodified'] = (d3['TOUCH_DETECT'] == 0 and d3['TOUCH1'] == 0 and d3['TOUCH2'] == 0)

  # bit 4: cluster passthrough when not active
  set_variant(CAND, 4, tmpdir)
  cl = CAND.create_lfahda_cluster(PACKER, mk_cs(), CAN, long_active=False, lat_active=False)
  d4 = PACKER.decode(*cl[0][:2])
  res['bit4_cluster_inactive_passthrough'] = (d4['HDA_LFA_SymSta'] == 1 and d4['HDA_CntrlModSta'] == 1)
  cl2 = CAND.create_lfahda_cluster(PACKER, mk_cs(), CAN, long_active=True, lat_active=True)
  d5 = PACKER.decode(*cl2[0][:2])
  res['bit4_cluster_active_forced_2'] = (d5['HDA_LFA_SymSta'] == 2 and d5['HDA_CntrlModSta'] == 2)
  set_variant(CAND, 0, tmpdir)
  cl0 = CAND.create_lfahda_cluster(PACKER, mk_cs(), CAN, long_active=False, lat_active=False)
  d6 = PACKER.decode(*cl0[0][:2])
  res['v0_cluster_forces_0'] = (d6['HDA_LFA_SymSta'] == 0 and d6['HDA_CntrlModSta'] == 0)

  # bit 8: DampingGain stays 100 while lat_active
  set_variant(CAND, 8, tmpdir)
  d7 = PACKER.decode(*by_name(PACKER, steer_msgs(CAND, 0, True, 90), 'LFA')[0][:2])
  res['bit8_damping_100_when_active'] = (d7['DampingGain'] == 100)
  set_variant(CAND, 0, tmpdir)
  d8 = PACKER.decode(*by_name(PACKER, steer_msgs(CAND, 0, True, 90), 'LFA')[0][:2])
  res['v0_damping_0_when_active'] = (d8['DampingGain'] == 0)

  # panda-safety sanity across variants: STEER_REQ==0 when not lat_active, TORQUE_REQUEST==apply_steer
  ok = True
  for v in (0, 1, 2, 4, 8, 15):
    set_variant(CAND, v, tmpdir)
    for la, st in ((False, 0), (False, 77), (True, 200)):
      dd = PACKER.decode(*by_name(PACKER, steer_msgs(CAND, 3, la, st), 'LFA')[0][:2])
      if dd['TORQUE_REQUEST'] != st or (not la and dd['STEER_REQ'] != 0) or (la and dd['STEER_REQ'] != 1):
        ok = False
  res['panda_safety_sanity_all_variants'] = ok

  res['all_passed'] = all(res.values())
  print(json.dumps(res, indent=1, sort_keys=True))
  return 0 if res['all_passed'] else 1


if __name__ == '__main__':
  sys.exit(main())
