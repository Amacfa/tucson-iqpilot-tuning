#!/usr/bin/env python3
"""P1 personality-write race test — simulates the button handler vs the 100 ms params_thread
re-read using a fake Params whose put_nonblocking defers the write until the next read cycle.

Original (rollback): press -> personality = (p-1)%3, put_nonblocking defers -> thread re-read
gets the STALE param value and overwrites self.personality -> press always shows same result.
Candidate: blocking put lands before the next thread read -> value sticks; presses cycle
standard(1) -> aggressive(0) -> relaxed(2) -> standard(1).
"""
import os, re, sys, json, textwrap

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(PKG, 'candidate/iqpilot/selfdrive/selfdrived/selfdrived.py')
ROLL = os.path.join(PKG, 'rollback/iqpilot/selfdrive/selfdrived/selfdrived.py')

res = {}
def chk(n, c, g=None): res[n] = bool(c); res[n + '_val'] = str(g)[:200]

src_c = open(CAND).read(); src_r = open(ROLL).read()

# --- structural: exactly one line differs, and it is the put ---
diff_lines = [(a, b) for a, b in zip(src_r.splitlines(), src_c.splitlines()) if a != b]
chk('one_line_changed', len(diff_lines) == 1 and len(src_r.splitlines()) == len(src_c.splitlines()), len(diff_lines))
chk('put_not_nonblocking', "self.params.put('LongitudinalPersonality', self.personality)" in src_c
    and "put_nonblocking('LongitudinalPersonality'" not in src_c)
chk('blocking_put_used_elsewhere', "self.params.put(" in src_c)  # consistent with existing usage

# extract the press-handler block (from the personality comment through experimental_mode_switched)
def extract(src):
    m = re.search(r'(^ *# decrement personality.*?experimental_mode_switched = False\n)', src, re.S | re.M)
    return textwrap.dedent(m.group(1)) if m else None

blk_c = extract(src_c); blk_r = extract(src_r)
chk('block_found_both', blk_c is not None and blk_r is not None)

# --- fake Params with deferred nonblocking writes ---
class FakeParams:
    def __init__(s):
        s.store = {'LongitudinalPersonality': 1}  # standard
        s.deferred = []
    def put(s, k, v):
        s.store[k] = v
    def put_nonblocking(s, k, v):
        s.deferred.append((k, v))
    def get(s, k):
        return s.store.get(k)
    def flush_deferred(s):
        # async writer lands *after* the thread's stale read
        for k, v in s.deferred: s.store[k] = v
        s.deferred.clear()

class Self:
    def __init__(s):
        s.params = FakeParams()
        s.personality = 1  # standard
        s.experimental_mode_switched = False
        s.events = set()
        s.CP = type('CP', (), {'openpilotLongitudinalControl': True})()

BE = type('BE', (), {'pressed': False, 'type': 'gapAdjustCruise'})
BTN = {'ButtonType': type('B', (), {'gapAdjustCruise': 'gapAdjustCruise'})}
EVT = {'EventName': type('E', (), {'personalityChanged': 'pc'})}

def press_once(blk):
    s = Self()
    ns = dict(self=s, be=BE, **BTN, **EVT, any=any)
    # feed the guard conditions the snippet expects
    ns['CS'] = type('CS', (), {'buttonEvents': [BE()]})()
    exec(compile(blk, '<p>', 'exec'), ns)
    return s

def press_and_thread(blk):
    """press -> handler runs -> params_thread re-read happens before deferred write lands."""
    s = press_once(blk)
    # thread re-read: personality = param value (deferred write not yet applied)
    s.personality = s.params.get('LongitudinalPersonality')
    s.params.flush_deferred()
    return s

# race simulation
s = press_and_thread(blk_r)
chk('race_rollback_reverts', s.personality == 1, s.personality)  # snapped back to standard
s = press_and_thread(blk_c)
chk('race_candidate_sticks', s.personality == 0, s.personality)  # aggressive stays

# 3 presses cycle standard->aggressive->relaxed->standard on the candidate
s = Self()
seen = [s.personality]
for _ in range(3):
    ns = dict(self=s, be=BE, **BTN, **EVT, any=any)
    ns['CS'] = type('CS', (), {'buttonEvents': [BE()]})()
    exec(compile(blk_c, '<p>', 'exec'), ns)
    s.personality = s.params.get('LongitudinalPersonality')  # thread re-read (blocking put already landed)
    seen.append(s.personality)
chk('cycle_1_0_2_1', seen == [1, 0, 2, 1], seen)

res['all_passed'] = all(v for k, v in res.items() if not k.endswith('_val'))
print(json.dumps(res, indent=1, sort_keys=True))
sys.exit(0 if res['all_passed'] else 1)
