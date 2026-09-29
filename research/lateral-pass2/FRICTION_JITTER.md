# Friction term + 40 mph jitter + handback-on-v3 (v3b)

Script: `/home/ubuntu/tucson/analysis/wobble/friction_jitter.py`, sims via
`sim_friction.py` (monkeypatches; sim scripts unchanged).

**Field caveat (precise):** torqueState exports `p, i, d, f, output` only — there is **no
separate friction field**. `pid_log.f` is the complete feedforward in lat-accel space
(future desired lat accel − latAccelOffset + friction contribution). Analysis converts `f`
and `p` to torque units via the release table (÷3.35–3.70 by speed) so RMS ratios vs `tq`
are comparable. "Friction" stats below are really **f-term** stats — friction cannot be
isolated from the logged data.

## 1. Oscillation episodes (same detector as closeout_v3b: 3 s windows, err band-frac>0.6, amp>0.4)

| group | bin | n | corr(f,p) med | corr(f,rate) med | frac anti-phase | frac \|corr\|>0.5 | f/tq rms med | dominant torque freq |
|---|---|---|---|---|---|---|---|---|
| baseline | 10–15 | 1 | −0.13 | 0.45 | 0.00 | 0.00 | 1.63 | {1.3: 1} |
| baseline | 15–20 | 10 | 0.55 | −0.01 | 0.10 | 0.50 | 1.46 | {0.3:2, 1.3:4, 1.7:4} |
| baseline | other | 3 | 0.32 | −0.24 | 0.00 | 0.00 | 1.55 | {1.3:1, 1.7:2} |
| v1_route24 | 10–15 | 1 | 0.80 | −0.03 | 0.00 | 1.00 | 0.74 | {1.3:1} |
| v2 | 15–20 | 2 | 0.70 | −0.04 | 0.00 | 1.00 | 1.17 | {1.7:2} |

Reading: inside episodes, **f and p oscillate IN phase** (corr 0.55–0.80, not anti-phase
lockstep — the handback-style friction-vs-P hunt signature is absent); f does not track
steering rate (corr ≈ 0). Dominant episode frequency is **1.3–1.7 Hz** (both v2 episodes at
1.7 Hz) — faster than a classic friction deadband hunt (~0.5–1 Hz), consistent with the
v1 regression being a 60 ms measurement-filter artifact (now removed in v2; only 2 episodes
remain, both 1.7 Hz). The f term's RMS during episodes is ~1.2–1.5× the total torque RMS —
expected: f carries the whole desired-accel waveform.

## 2. Straight steady stretches (|dla|<0.3), RMS of torque-space terms

| group | n windows | rms_f | rms_p | rms_tq | f/tq |
|---|---|---|---|---|---|
| 0b8c190c | 157 | 0.057 | 0.020 | 0.050 | 1.11 |
| baseline | 973 | 0.060 | 0.023 | 0.046 | 1.30 |
| v1_route24 | 28 | 0.046 | 0.021 | 0.055 | 0.78 |
| v2 | 241 | 0.060 | 0.019 | 0.047 | 1.29 |

On straights, ~all torque RMS is the f term wiggling (P contributes only ~0.02). v2's f RMS
equals baseline — v2 did not reduce feedforward dither on straights; it only fixed the
episode mechanism.

## 3. Friction sensitivity sims (v3 table; handback excitation = route 26 seg 6 real data)

| config | ala_pp | ala_rms | band_1–3 | tq_pp | track_rms |
|---|---|---|---|---|---|
| v3, friction 0.12 | 1.033 | 0.297 | 0.929 | 0.289 | 0.297 |
| v3, friction 0.09 | 1.115 | 0.299 | 0.841 | 0.272 | 0.297 |
| v3, friction 0.06 | 0.979 | 0.267 | 0.945 | 0.273 | 0.263 |
| v2, friction 0.12 (ref) | 1.021 | 0.291 | 0.933 | 0.273 | 0.291 |

Curve-exit (v2_frames, 12 exits): friction 0.12/0.09/0.06 → band_tq 0.518/0.515/0.511,
dither 2.17/2.15/2.12 under v3 — **weakly monotonic; friction magnitude is not the jitter
lever in the sims**.

## 4. Handback fix on tune-v3 (lanechange candidate: P ×0.6 above ~30 mph + 0.3 s friction-input LP)

| config | ala_pp | ala_rms | band_1–3 | tq_pp | track_rms |
|---|---|---|---|---|---|
| v3 base | 1.033 | 0.297 | 0.929 | 0.289 | 0.297 |
| v3 + P×0.6 >15 m/s | 0.978 | 0.272 | 0.892 | 0.281 | 0.258 |
| v3 + 0.3 s friction LP | 0.962 | 0.283 | 0.904 | 0.273 | 0.273 |
| **v3 + fix C (both)** | **0.507** | **0.107** | **0.629** | **0.162** | **0.098** |

The fix's benefit carries over to the v3 table and the two halves are complementary —
combined it roughly **halves** the simulated handback excursion (ala_pp 1.03→0.51) and cuts
the 1–3 Hz band content 0.93→0.63. Real-drive check pending any install; sim is directional.
