#!/usr/bin/env python3
"""Hourly research refresh: pull new drive segments from the comma, rebuild the
frame dataset, produce a pre/post-install A/B report, publish to github-record
and the Mac snapshot. Idempotent; read-only w.r.t. the device (writes only to
/data/tucson_stage and /data/tucson-drive-export, as before).

stdout emits one compact JSON summary line.
"""
import gzip
import json
import os
import re
import subprocess
import sys
import datetime

HOME = '/home/ubuntu/tucson'
HOURLY = f'{HOME}/hourly'
STATE = f'{HOURLY}/state/segments.json'
EXPORT_DIR = f'{HOME}/drives/export'
FRAMES = f'{HOME}/drives/all_frames.npy'
COLS = f'{HOME}/drives/all_frames_cols.json'
REPORTS = f'{HOURLY}/reports'
GH = f'{HOME}/github-record'
DEVICE_EXPORTER_LOCAL = f'{HOME}/drives/export_drive_summary_v2.py'
DEVICE_EXPORTER = '/data/tucson_stage/export_drive_summary_v2.py'
DEVICE_OUT = '/data/tucson-drive-export-v2'
DEVICE_BASE = '/data/media/0/realdata'
VENV = '/data/openpilot/.venv/bin/python'
PPATH = '/data/openpilot/.venv/lib/python3.12/site-packages:/data/openpilot'
ARMING_MANIFEST = f'{HOME}/analysis/tucson-warning-arming-457ea8e/package/manifest.json'
TUNE_MANIFEST = f'{HOME}/analysis/tucson-tune-457ea8e/package/manifest.json'
INSTALL_UTC = datetime.datetime(2026, 9, 24, 7, 40, 0, tzinfo=datetime.timezone.utc).timestamp()
MAC_DIR = '/Users/Shared/tucson-llm-handoff-20260923/analysis/hourly-research'

warnings = []


def sh(cmd, timeout=120, capture=True):
    return subprocess.run(cmd, shell=True, capture_output=capture, text=True, timeout=timeout)


def comma(remote_cmd, timeout=120):
    import base64
    b64 = base64.b64encode(remote_cmd.encode()).decode()
    inner = f"echo {b64} | base64 -d | bash"
    return sh(f"ssh -o ConnectTimeout=10 mac 'ssh -o ConnectTimeout=20 comma \"{inner}\"'", timeout)


def ts_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def summary(**kw):
    print(json.dumps(kw, sort_keys=True))


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    # Seed from existing exports so the first run does not re-export history.
    segs = {}
    for f in sorted(os.listdir(EXPORT_DIR)):
        if f.endswith('.jsonl.gz'):
            segs[f[:-9]] = {'epoch': 'pre-install', 'exported_utc': 'pre-index'}
    return {'segments': segs, 'created_utc': ts_now()}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + '.tmp'
    json.dump(st, open(tmp, 'w'), indent=1)
    os.replace(tmp, STATE)


def inventory():
    """Return {seg: mtime_epoch} for device segment dirs with rlog.zst."""
    r = comma(f"cd {DEVICE_BASE} && for d in *--*; do "
              f"test -f $d/rlog.zst && echo $d $(stat -c %Y $d/rlog.zst); done")
    if r.returncode != 0:
        raise RuntimeError('inventory failed: ' + r.stderr[:300])
    out = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            out[parts[0].rsplit('/', 1)[0]] = int(float(parts[-1]))
    return out


def device_facts():
    facts = {}
    r = comma('cd /data/openpilot && git rev-parse HEAD')
    facts['head'] = r.stdout.strip() if r.returncode == 0 else None
    r = comma('cd /data/openpilot && git status --porcelain | head -50')
    facts['dirty_files'] = [l.strip() for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []
    # installed-hash check: candidate hashes from both manifests
    checks = {}
    for mp in (ARMING_MANIFEST, TUNE_MANIFEST):
        m = json.load(open(mp))
        for e in m['files']:
            checks[e['path']] = e['candidate_sha256']
    # pandad binary is rebuilt at boot from pandad.cc -> check source only
    r = comma('cd /data/openpilot && sha256sum ' + ' '.join(checks))
    dev = {}
    for line in r.stdout.splitlines():
        h, _, path = line.partition('  ')
        dev[path.strip()] = h
    facts['installed_files'] = {p: ('match' if dev.get(p) == h or (p == 'iqpilot/selfdrive/pandad/pandad')
                                    else f'MISMATCH {dev.get(p)}') for p, h in checks.items()}
    return facts


def export_new(new_segs):
    """Run the device exporter for new segs, pull results. Returns per-seg status."""
    # Ensure exporter script present on device
    r = comma(f'test -f {DEVICE_EXPORTER} && echo present')
    if 'present' not in r.stdout:
        data = open(DEVICE_EXPORTER_LOCAL, 'rb').read()
        p = subprocess.run(f"ssh -o ConnectTimeout=10 mac 'ssh -o ConnectTimeout=20 comma \"cat > {DEVICE_EXPORTER}\"'",
                           shell=True, input=data, capture_output=True, timeout=60)
        if p.returncode != 0:
            raise RuntimeError('could not stage exporter')
    statuses = {}
    CHUNK = 12
    for i in range(0, len(new_segs), CHUNK):
        chunk = new_segs[i:i + CHUNK]
        r = comma(f"cd /data/openpilot && PYTHONPATH={PPATH} {VENV} {DEVICE_EXPORTER} "
                  + ' '.join(chunk), timeout=600)
        statuses.update(dict.fromkeys(chunk, r.stdout.strip()[-2000:] if r.stdout else r.stderr.strip()[-500:]))
    pulled = []
    for seg in new_segs:
        src = f'{DEVICE_OUT}/{seg}.jsonl.gz'
        dst = f'{EXPORT_DIR}/{seg}.jsonl.gz'
        p = subprocess.run(f"ssh -o ConnectTimeout=10 mac 'ssh -o ConnectTimeout=20 comma \"cat {src}\"' > {dst}",
                           shell=True, capture_output=True, timeout=120)
        if p.returncode == 0 and os.path.getsize(dst) > 100:
            pulled.append(seg)
        else:
            os.path.exists(dst) and os.remove(dst)
            statuses[seg] += ' PULL_FAILED'
            warnings.append(f'pull failed: {seg}')
    return pulled, statuses


def rebuild_frames():
    r = sh(f"/usr/bin/python3 {HOME}/drives/build_long.py", timeout=600)
    if r.returncode != 0:
        raise RuntimeError('build_long failed: ' + r.stderr[-500:])
    return r.stdout.strip()


def seg_epoch_map(state):
    return {s: d.get('epoch', 'pre-install') for s, d in state['segments'].items()}


def epoch_events():
    """Parse meta lines of all exports -> per-epoch event/alert counters."""
    import collections
    ev = {'pre-install': collections.Counter(), 'post-install': collections.Counter()}
    pat_fault = re.compile(r'steer|lka|lfa|ldw|lane|fault|warn', re.I)
    pat_lfa = re.compile(r'lfa|lkas|laneKeep|preLane|steer.*(unavail|reject|warn)|lfda', re.I)
    for f in sorted(os.listdir(EXPORT_DIR)):
        if not f.endswith('.jsonl.gz'):
            continue
        seg = f[:-9]
        try:
            with gzip.open(f'{EXPORT_DIR}/{f}', 'rt') as g:
                meta = json.loads(g.readline())['meta']
        except Exception:
            continue
        for tt, w, names in meta.get('events', []):
            for n in names:
                if pat_fault.search(str(n)):
                    ev[seg_epoch_map(STATE_OBJ).get(seg, 'pre-install')][str(n)] += 1
                if str(n) == 'fcw':
                    ev[seg_epoch_map(STATE_OBJ).get(seg, 'pre-install')]['fcw'] += 1
        for tt, t1, t2, status, state in meta.get('alerts', []):
            if pat_fault.search(str(t1) + str(t2)):
                ev[seg_epoch_map(STATE_OBJ).get(seg, 'pre-install')][f'alert:{status}'] += 1
            if pat_lfa.search(str(t1) + str(t2)):
                ev[seg_epoch_map(STATE_OBJ).get(seg, 'pre-install')]['lfa_like_alert'] += 1
    return ev


STATE_OBJ = None


def analyze(epoch_of_seg):
    import numpy as np
    A = np.load(FRAMES)
    C = json.load(open(COLS))
    ix = {c: i for i, c in enumerate(C)}

    def col(n):
        return A[:, ix[n]]
    rid, seg = col('rid').astype(int), col('seg').astype(int)
    segname = np.array([f'{r:08x}--{s}' for r, s in zip(rid, seg)])
    # rid is int(hexprefix): segment name in exports is <8hex>--<hash>--<n>; rid only
    # encodes the first hex group, so map epoch by (rid,seg) via export name prefix.
    ep = {}
    for name, e in epoch_of_seg.items():
        pre, _, sn = name.rpartition('--')
        try:
            ep[(int(pre.split('--')[0], 16), int(sn))] = e
        except ValueError:
            pass
    epoch = np.array([ep.get((int(r), int(s)), 'pre-install') for r, s in zip(rid, seg)])

    cols = {n: col(n) for n in ['t', 'v', 'a', 'acc', 'lon', 'en', 'cen', 'gas', 'brk', 'ss', 'curv',
                                'ala', 'dla', 'tq', 'tqo', 'p', 'i', 'f', 'out', 'err', 'act', 'prs',
                                'ang', 'rate', 'sat', 'dtq', 'yaw', 'lat']}
    out = {}
    BINS = [(5, 10), (10, 15), (15, 20), (20, 25), (25, 40)]
    for ep_name in ('pre-install', 'post-install'):
        em = epoch == ep_name
        res = {'frames': int(em.sum())}
        if em.sum() < 1000:
            res['note'] = 'insufficient data'
            out[ep_name] = res
            continue
        act = em & (cols['act'] == 1)
        good = act & (cols['prs'] == 0) & (cols['lat'] == 1)
        res['active_hours'] = round(float(act.sum()) / 360000, 3)

        # torque dither RMS (x270) by speed bin, contiguous active frames
        same = (rid[1:] == rid[:-1]) & (seg[1:] == seg[:-1])  # length N-1, indexed to frame i+1
        dtq = np.abs(np.diff(cols['tqo'])) * 270
        ok = same & (cols['act'][1:] == 1) & (cols['act'][:-1] == 1) & em[1:]
        vv = cols['v'][1:]
        res['dither_rms_x270'] = {f'{lo}-{hi}': round(float(np.sqrt(np.mean(dtq[ok & (vv >= lo) & (vv < hi)] ** 2))), 3)
                                for lo, hi in BINS if (ok & (vv >= lo) & (vv < hi)).sum() > 200}
        # actual/requested lat accel ratio by speed bin (|dla|>0.3)
        res['lataccel_ratio'] = {}
        m0 = good & (np.abs(cols['dla']) > 0.3)
        for lo, hi in BINS:
            m = m0 & (cols['v'] >= lo) & (cols['v'] < hi)
            if m.sum() > 300:
                res['lataccel_ratio'][f'{lo}-{hi}'] = round(float(
                    np.median(cols['ala'][m] * np.sign(cols['dla'][m])) / np.median(np.abs(cols['dla'][m]))), 3)
        res['p_oppose_ff_frac'] = round(float(
            (np.sign(cols['p'][m0]) != np.sign(cols['f'][m0])).mean()), 3) if m0.sum() else None
        res['steer_sat_pct'] = round(100 * float((good & (cols['sat'] == 1)).sum()) / max(good.sum(), 1), 3)
        res['tq_over_095_pct'] = round(100 * float((good & (np.abs(cols['tqo']) > 0.95)).sum()) / max(good.sum(), 1), 3)

        # steering overrides >=0.3s while lat active
        pr = (cols['prs'] == 1) & (cols['lat'] == 1) & em
        idx = np.flatnonzero(pr)
        eps = 0
        if len(idx):
            s0 = pidx = idx[0]
            for k in idx[1:]:
                if k != pidx + 1:
                    if pidx - s0 >= 30:
                        eps += 1
                    s0 = k
                pidx = k
            if pidx - s0 >= 30:
                eps += 1
        res['steer_overrides_per_hr'] = round(eps / max(res['active_hours'], 1e-6), 1)

        # ---- longitudinal ----
        lon = em & (cols['lon'] == 1) & (cols['en'] == 1)
        res['long_hours'] = round(float(lon.sum()) / 360000, 3)
        a_, acc, v_ = cols['a'], cols['acc'], cols['v']
        # cmd-vs-actual lag: best corr shift 0..2s on lon frames
        lags = []
        idxl = np.flatnonzero(lon & (v_ > 5))
        for s in range(0, len(idxl) - 500, 500):
            ids = idxl[s:s + 500]
            x, y = acc[ids] - acc[ids].mean(), a_[ids] - a_[ids].mean()
            if x.std() < 0.1 or y.std() < 0.1:
                continue
            best = max(range(0, 200, 5), key=lambda L: np.corrcoef(x[:-L or None], y[L:])[0, 1] if L else np.corrcoef(x, y)[0, 1])
            lags.append(best / 100)
        res['cmd_lag_s'] = round(float(np.median(lags)), 2) if lags else None
        mpos = lon & (acc > 1.0) & (v_ > 3)
        mneg = lon & (acc < -1.0) & (v_ > 3)
        res['pos_step_ratio'] = round(float(np.median(a_[mpos] / acc[mpos])), 3) if mpos.sum() > 200 else None
        res['neg_step_ratio'] = round(float(np.median(a_[mneg] / acc[mneg])), 3) if mneg.sum() > 200 else None
        dl = same & (lon[1:] == 1) & (lon[:-1] == 1) & em[1:]
        res['jerk_rms'] = round(float(np.sqrt(np.mean((np.diff(a_)[dl] * 100) ** 2))), 3) if dl.sum() else None
        # stop-end accel: cmd in final 1s before standstill
        stops = np.flatnonzero((cols['ss'][1:] == 1) & (cols['ss'][:-1] == 0) & (lon[:-1] == 1) & em[:-1]) + 1
        stops = stops[(stops >= 100) & (rid[np.clip(stops - 100, 0, len(A) - 1)] == rid[np.clip(stops, 0, len(A) - 1)])]
        res['stop_end_cmd'] = round(float(np.mean([acc[s - 100:s].mean() for s in stops])), 3) if len(stops) else None
        # launch accel: peak a within 3s of leaving standstill while lon
        launches = np.flatnonzero((cols['ss'][1:] == 0) & (cols['ss'][:-1] == 1) & (lon[:-1] == 1) & em[:-1]) + 1
        launches = launches[(launches + 300 < len(A)) & (rid[launches + 300] == rid[launches])]
        res['launch_peak_a'] = round(float(np.mean([a_[s:s + 300].max() for s in launches])), 3) if len(launches) else None
        en = em & (cols['en'] == 1)
        gasr = np.diff((cols['gas'] == 1).astype(int)) == 1
        brkr = np.diff((cols['brk'] == 1).astype(int)) == 1
        res['gas_overrides_per_hr'] = round(float((gasr & en[1:]).sum()) / max(res['active_hours'], 1e-6), 1)
        res['brake_overrides_per_hr'] = round(float((brkr & en[1:]).sum()) / max(res['active_hours'], 1e-6), 1)
        out[ep_name] = res
    return out


def build_report(ts, new_segs, epoch_of_seg, facts, statuses, metrics, ev, duration):
    lines = [f'# Research refresh {ts}', '']
    if not new_segs:
        lines.append('No new data.')
        return '\n'.join(lines) + '\n'
    lines.append(f'New segments: {len(new_segs)} (total exported duration {duration:.0f} s)')
    lines.append(f'Device HEAD: {facts.get("head")}; dirty files: {len(facts.get("dirty_files", []))}')
    bad = {p: s for p, s in facts.get('installed_files', {}).items() if s != 'match'}
    lines.append(f'Installed-file hash check: {"all candidate" if not bad else bad}')
    lines.append('')
    for ep in ('pre-install', 'post-install'):
        m = metrics[ep]
        lines.append(f'## {ep} ({"baseline" if ep == "pre-install" else "A/B result"})')
        if 'note' in m:
            lines.append(f"{m['note']} ({m['frames']} frames)"); lines.append(''); continue
        lines.append(f"active hours {m['active_hours']}, long hours {m['long_hours']}")
        lines.append('### Steering')
        lines.append(f"- torque dither RMS x270 by speed: {m['dither_rms_x270']}")
        lines.append(f"- actual/requested latAccel ratio by speed: {m['lataccel_ratio']}")
        lines.append(f"- P opposing FF fraction: {m['p_oppose_ff_frac']}")
        lines.append(f"- steer saturation: {m['steer_sat_pct']}% (|tqo|>0.95: {m['tq_over_095_pct']}%)")
        lines.append(f"- driver steering overrides: {m['steer_overrides_per_hr']}/active-hr")
        lines.append(f"- steering/LKA/LFA-related events: {dict(ev.get(ep, {}))}")
        lines.append('### Longitudinal')
        lines.append(f"- cmd-vs-actual lag: {m['cmd_lag_s']} s")
        lines.append(f"- pos/neg step ratios: {m['pos_step_ratio']} / {m['neg_step_ratio']}")
        lines.append(f"- jerk RMS: {m['jerk_rms']} m/s^3")
        lines.append(f"- stop-end cmd accel: {m['stop_end_cmd']}; launch peak accel: {m['launch_peak_a']}")
        lines.append(f"- gas/brake overrides: {m['gas_overrides_per_hr']} / {m['brake_overrides_per_hr']} per active-hr")
        lines.append('')
    return '\n'.join(lines) + '\n'


def sanitize(text):
    text = re.sub(r'\-\-[0-9a-f]{6,}', '--<redacted>', text)
    return text


def publish(ts, report):
    rdir = f'{GH}/research'
    os.makedirs(rdir, exist_ok=True)
    path = f'{rdir}/{ts}.md'
    open(path, 'w').write(sanitize(report))
    idx = f'{rdir}/INDEX.md'
    entries = sorted(f for f in os.listdir(rdir) if re.match(r'\d{8}T\d{6}Z\.md$', f))
    open(idx, 'w').write('# Hourly research reports\n\n' + '\n'.join(f'- [{e[:-3]}]({e})' for e in entries) + '\n')
    sh(f"cd {GH} && git add research && git diff --cached --quiet && exit 7 || true")
    r = sh(f"cd {GH} && git commit -m 'hourly research refresh {ts}' && git rev-parse HEAD", timeout=60)
    if r.returncode == 0:
        sh(f'cd {GH} && git push origin main', timeout=60)
        return r.stdout.strip().splitlines()[-1]
    return None


def mac_copy(path, ts):
    r = sh(f"ssh -o ConnectTimeout=10 mac 'mkdir -p {MAC_DIR}'", timeout=30)
    if r.returncode != 0:
        warnings.append('mac unreachable; snapshot copy skipped')
        return False
    sh(f"scp -o ConnectTimeout=10 {path} mac:{MAC_DIR}/{ts}.md", timeout=60)
    return True


def main():
    global STATE_OBJ
    ts = ts_now()
    status = {'reachable': False}
    r = comma('true', timeout=40)
    if r.returncode != 0:
        status['ts'] = ts
        os.makedirs(f'{HOURLY}/state', exist_ok=True)
        json.dump(status, open(f'{HOURLY}/state/last_status.json', 'w'))
        summary(**status, new_segments=0, report_path=None, pushed_commit=None, warnings=['comma unreachable'])
        return
    status['reachable'] = True
    STATE_OBJ = load_state()
    try:
        inv = inventory()
    except Exception as e:
        summary(**status, error=str(e), new_segments=0, report_path=None, pushed_commit=None, warnings=[str(e)])
        return
    try:
        facts = device_facts()
    except Exception as e:
        warnings.append(f'device facts failed: {e}')
        facts = {}
    status.update(facts)
    known = set(STATE_OBJ['segments'])
    local = {f[:-9] for f in os.listdir(EXPORT_DIR) if f.endswith('.jsonl.gz')}
    new_segs = sorted(s for s in inv if s not in known and s not in local)
    post = [s for s in new_segs if inv[s] >= INSTALL_UTC]
    pulled, statuses = ([], {})
    if new_segs:
        pulled, statuses = export_new(new_segs)
        for s in pulled:
            STATE_OBJ['segments'][s] = {'epoch': 'post-install' if inv[s] >= INSTALL_UTC else 'pre-install',
                                        'mtime': inv[s], 'exported_utc': ts}
        # Record unpulled (failed) segments so they are not retried every hour.
        for s in new_segs:
            if s not in pulled:
                STATE_OBJ['segments'][s] = {'epoch': 'post-install' if inv[s] >= INSTALL_UTC else 'pre-install',
                                            'mtime': inv[s], 'failed': True,
                                            'error': statuses.get(s, '')[-200:]}
                warnings.append(f'export failed (recorded, will not retry): {s}')
        save_state(STATE_OBJ)
    report_path = None
    pushed = None
    if pulled:
        rebuild_frames()
        ep_of = seg_epoch_map(STATE_OBJ)
        metrics = analyze(ep_of)
        ev = epoch_events()
        duration = len(pulled) * 60.0
        report = build_report(ts, pulled, ep_of, facts, statuses, metrics, ev, duration)
        os.makedirs(REPORTS, exist_ok=True)
        report_path = f'{REPORTS}/{ts}.md'
        open(report_path, 'w').write(report)
        if os.environ.get('REFRESH_NO_PUBLISH'):
            warnings.append('publish skipped (REFRESH_NO_PUBLISH)')
        else:
            pushed = publish(ts, report)
            mac_copy(report_path, ts)
    else:
        os.makedirs(REPORTS, exist_ok=True)
        report_path = f'{REPORTS}/{ts}.md'
        open(report_path, 'w').write(f'# Research refresh {ts}\n\nNo new data.\n')
        if new_segs and not pulled:
            warnings.append('new segments found but none pulled')
    summary(reachable=True, new_segments=len(new_segs), post_install_segments=len(post),
            pulled=len(pulled), report_path=report_path, pushed_commit=pushed,
            head=facts.get('head'), warnings=warnings)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        summary(reachable=None, error=str(e), warnings=warnings)
        sys.exit(0)
