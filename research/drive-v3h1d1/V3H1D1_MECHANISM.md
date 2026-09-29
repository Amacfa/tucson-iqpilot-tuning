# Mechanism analysis: curve-exit tr 1.44 & saturation 1.12% (route 0000002d, v3+H1+D1)

Method: faithful open-loop replay of the **installed** latcontrol_torque logic (dt=0.01, KP_INTERP×0.8 reduced-feedback, KI=0.15, slew limiter, JERK_GAIN friction input, H1 kp interp 13→17→[1.0,0.6], H1 0.3 s friction-error LP, v3 LAF table). Recorded `dla` is the *post-lookahead* setpoint (delay 0.15 s), so the buffer input is reconstructed as `dla` back-shifted 0.15 s. Validation: replay at delay=0.15+LP must reproduce recorded `-tqo`.

**Replay fidelity**: rmse 0.03–0.38 normalized torque, corr 0.45–0.93 per segment (open-loop: measurement = recorded ala; residual error is expected). Directional deltas between variants are small relative to this uncertainty — treated as upper bounds.

## Verdicts

### H-a (D1 lookahead 0.30→0.15 caused exit over-turn) — NOT the torque mechanism, but YES the *metric* mechanism

- Exit-window replay torque diff (0.30 vs 0.15): **±0.03–0.16, mean |Δ|≈0.05**; FF diff ≤0.03. Neither reproduces recorded exit torque better — recorded ≈ replay015 in every window.
- **But the observed tr_exit inflation IS largely a D1 timing artifact on the denominator**: `dla` is `buf[-delay_frames]`. At an unwind ramping −2.5…−4 m/s³, setpoint at 0.15 s delay is **~0.4–0.6 m/s² lower** than at 0.30 s during the last-0.6 s window → `mean|dla|` shrinks → measured ratio rises ~1.1→~1.4 without any extra torque. tr_exit here = mean(ala·sign(dla))/mean(|dla|) on the last 0.6 s *inside* the demand — it is a ratio metric, sensitive to setpoint timing, not an energy measure. Same detector as v2/baseline (no bug, symmetric) — but its value shifts when lookahead changes, so **v3h1d1 vs v2 tr_exit comparison is confounded by the metric**.
- Per-curve tr_exit (v, tr): all 9 curves elevated — (6.3,1.43)(5.8,1.50)(7.4,1.67)(14.2,1.46)(11.9,1.56)(11.4,1.21)(7.7,1.29)(5.7,1.16)(6.9,1.68) → mean 1.47 vs v2 v<15 **1.09** (n=38, same detector) and baseline v<15 1.13 (n=106). Real, uniform, not one outlier.
- Component-wise, recorded exit torque ≈ both replays; the residual over-rotation is plant un-wind lag the metric can't distinguish.

### H-b (H1 friction-error LP 0.3 s holding friction into the unwind) — NOT supported

- LP on/off replay diff at exits: **≤0.005 normalized torque** in every window. The LP'd error is already small at exits (setpoint tracks actual closely during unwind); JERK_GAIN·jerk term dominates the friction input there and is unaffected by the LP.

### H-c (saturation) — real demand saturation, clustered, FF-driven (not P)

7 events, ~10.7 s total (≈1.1% of active frames — matches the 1.12%):

| seg@t | dur | v | context | |dla| | mean|p| | mean|f| |
|---|---|---|---|---|---|---|---|---|
| 5 @15.9 | 2.19 s | 7.4 | override settle | 3.00 | 2.47 | 2.92 |
| 5 @46.3 | 4.40 s | 11.8 | tight curve | 3.00 | 0.37 | 3.47 |
| 5 @59.9 | 0.07 s | 12.2 | curve | 2.76 | 0.17 | 3.49 |
| 6 @0.0 | 1.15 s | 11.9 | curve | 3.00 | 0.22 | 3.51 |
| 6 @13.4 | 0.04 s | 11.4 | override | 2.93 | 0.38 | 3.20 |
| 6 @28.9 | 0.81 s | 7.1 | curve | 3.00 | 0.95 | 2.91 |
| 9 @9.1 | 1.54 s | 6.6 | override settle | 3.00 | 2.62 | 2.98 |

- **FF-dominated**: f (lataccel units, incl. friction) runs 2.9–3.5 while p is 0.2–0.95 (except the two low-speed override-settle events where P ~2.5 leads briefly). `|dla|` pinned at **3.0 = the slew limiter's A_LAT_MAX cap** — the planner/model demanded ≥3.5 m/s² in tight low-speed corners; torque out = f/K ≈ 3.4/3.2 ≈ 1.06 → clipped.
- Why 30× v2: partly **drive content** (this route is unusually tight low-speed turning — roundabouts/parking), partly real — with demanded lataccel ≈3.5 vs pid pos_limit = K(v)·steer_max ≈ 3.2–3.9, every such corner clips. Not P-instability; the override-settle events (5@15.9, 9@9.1) are P-heavy and are where the felt wobble lives.

### v3 table gain (bonus check)
Replay with the v2 table vs v3 table: mean exit torque diff **0.002** — the higher K is not measurably slowing the unwind in torque terms.

## Bottom line for v4 design

1. The "aggressive exit" feeling is real behavior (car holds rotation while demand unwinds) but **the 1.44 headline number is inflated by the D1 lookahead shifting the dla reference earlier** — design a fix on torque/angle data, not on chasing that ratio.
2. Saturation is **demand saturation at the A_LAT_MAX=3.0 slew cap in tight low-speed turns**, FF-driven. Candidate v4 lever: cap demanded lataccel lower (or soften slew bypass) below ~12 m/s; P is not the sat driver.
3. Neither H1's friction LP nor D1's lookahead produced harmful torque signatures in replay — both look clean; the remaining real knob for comfort is the low-speed (≤13 m/s) P strength (the two P-heavy override-settle sats + the 1.7 Hz episode at 10.8 m/s are all below H1's 13 m/s ramp).

Script: `mechanism_v3h1d1.py` (replay + saturation census + per-curve list).
