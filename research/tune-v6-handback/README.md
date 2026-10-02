# tune-v6 — hand-back friction reset (offline candidate, NOT installed)

Single-file change to `iqpilot/selfdrive/controls/lib/latcontrol_torque.py` on
top of installed v5. Adds `LAT_TUNE_V6`, a per-car dict gated on
`HYUNDAI_TUCSON_4TH_GEN` — every other car runs the exact previous code path.

**What it does for the driver**: pressing the wheel and handing control back no
longer carries stale friction-compensation error into the first moments after
hand-back — the friction error memory resets while you hold the wheel, ramps
back over 0.25 s, and also resets on direction flips (curve exits). That is the
only behaviour change (knob B). Knob A (separate P/I scaling factor) is wired
but configured identical to the speed schedule, so it is neutral. Knob C
(delay smoothing) is off.

`torque_from_lateral_accel` is linear (`la/factor`), and `pid.update` still
clips the combined `p+i+f`, so the split is exact and limits are unchanged.

Package (manifest, manage.py, forward/reverse patches): `package/`.
Details + sim tables: `NOTES.md`. **Not installed — not yet driven.**
