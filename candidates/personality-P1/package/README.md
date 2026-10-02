# P1 — personality button fix (offline candidate, NOT installed)

## What
`iqpilot/selfdrive/selfdrived/selfdrived.py` — **one line**:
`self.params.put_nonblocking('LongitudinalPersonality', self.personality)` →
`self.params.put('LongitudinalPersonality', self.personality)` (blocking write,
same call the longitudinal settings helpers already use).

## Why
The gap/distance button handler (line ~586) writes the new personality with
`put_nonblocking` while `params_thread` re-reads `self.personality =
get_runtime_personality(self.params)` every ~100 ms. The async write lands
*after* the thread's stale read, so `self.personality` snaps back to the old
value — and the next press decrements from the same stale start, so every
press displays "Aggressive".

Logged timeline: `aggressive` at +0 ms after a press, `standard` again at
+67 ms (the thread re-read winning the race), next press → "Aggressive" again.

## Behaviour after fix
Each press cycles **standard → aggressive → relaxed → standard** and the value
the UI shows persists (blocking put completes before the next thread read).
The ~0.5 s long-hold that toggles Experimental Mode is a separate code path —
unchanged. All other params unchanged.

## Status
**NOT installed — offline candidate only** (`readiness: check_only`).
Independent of M1/L2/S2 (different file; no shared dependencies).
Rollback restores `68aa63da` exactly (`manage.py --rollback`, parked only).

## Validation
`validation/test_p1.py`: fake Params with deferred `put_nonblocking` — rollback
reverts under the simulated thread re-read, candidate sticks; 3 presses cycle
1→0→2→1. `test_artifacts.py` (hashes + patch roundtrip + py_compile) and
`test_manage.py` (7 guards) — all pass.
