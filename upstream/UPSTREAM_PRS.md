# Upstream PRs — Teal IQ.Pilot

Base: `release-candidate` @ `90078952` on https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot
Heads pushed from fork `rozal/IQ.Pilot`. Local branch commits below (in
`/home/ubuntu/tucson/upstream/IQ.Pilot`, author Alex Macfarlane).

| PR | branch | local commit | link |
|---|---|---|---|
| #23 | fix/personality-button-blocking-put | `895fde1` | https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/23 |
| #24 | hyundai/tucson-4th-gen-fw-cw020 | `4991462` | https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/24 |
| #25 | hyundai/tucson-canfd-startup-arming | `250398a` | https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/25 |
| #26 | hyundai/tucson-main-button-keeps-long (stacked on #25) | `4bfdacc` | https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/26 |
| #27 | cruise/set-adopts-current-speed | `4934b28` | https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/27 |
| #28 | hyundai/tucson-canfd-launch-smoothing | `1026647` | https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/28 |
| #29 | hyundai/tucson-lateral-tune | `e6254fd` | https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/29 |
| #30 | long/stop-and-cruise-tuning | `088a1f6` | https://git.konn3kt.com/IQ.Lvbs/IQ.Pilot/pulls/30 |

`PR_DESCRIPTIONS.md` = the PR bodies; `mkprs.py` = the script that opened
them (reads the Gitea token from the `GT` env var only — no token in the
repo).

**Excluded**: the `hyundaicanfd.py` LFA-AB variant switch — variant 0 is
byte-identical to unpatched, so there was nothing to merge.
