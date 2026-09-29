#!/usr/bin/env python3
"""Hourly research refresh (v3b pipeline): pull new drive segments from the comma
with export_drive_summary_v3.py, run the long3b attribution + steering closeout,
produce a report, publish to github-record and the Mac snapshot. Idempotent;
read-only w.r.t. the device (writes only to /data/tucson_stage and
/data/tucson-drive-export-v3b).

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
STATE = f'{HOURLY}/state/segments_v3.json'
EXPORT_DIR = f'{HOME}/drives/export-v3b'
REPORTS = f'{HOURLY}/reports'
GH = f'{HOME}/github-record'
DEVICE_EXPORTER_LOCAL = f'{HOME}/drives/export_drive_summary_v3.py'
DEVICE_EXPORTER = '/data/tucson_stage/export_drive_summary_v3.py'
DEVICE_OUT = '/data/tucson-drive-export-v3b'
DEVICE_BASE = '/data/media/0/realdata'
VENV = '/data/openpilot/.venv/bin/python'
PPATH = '/data/openpilot/.venv/lib/python3.12/site-packages:/data/openpilot'
# manifests used for the installed-state check: (label, manifest, origin)
MANIFESTS = [
    ('tune-v2', f'{HOME}/analysis/tucson-tune-3736edc-v2/package/manifest.json'),
    ('lfa-ab', f'{HOME}/analysis/tucson-lfa-ab-3736edc/package/manifest.json'),
    ('arming', f'{HOME}/analysis/tucson-warning-arming-3736edc/package/manifest.json'),
]
CANDIDATE_ONLY = [  # report presence only (L1c/C1 never installed; v3/H1/D1 installed 2026-09-29)
    ('tune-v3', f'{HOME}/analysis/tucson-tune-3736edc-v3/package/manifest.json'),
    ('H1', f'{HOME}/analysis/tucson-tune-3736edc-H1/package/manifest.json'),
    ('D1', f'{HOME}/analysis/tucson-tune-3736edc-D1/package/manifest.json'),
    ('L1c', f'{HOME}/analysis/tucson-long-3736edc-L1c/package/manifest.json'),
    ('C1', f'{HOME}/analysis/tucson-setspeed-3736edc-C1/package/manifest.json'),
]
CLOSEOUT = f'{HOME}/analysis/wobble/closeout_v3b.py'
ATTRIB = f'{HOME}/drives/long3/attribute_long3b.py'
MAC_DIR = '/Users/Shared/tucson-llm-handoff-20260923/analysis/hourly-research'
# known-truncated segments: pre-mark failed at seed so they are never retried
KNOWN_BAD = {'00000029--af0e2ac1ba--9', '00000002--8b575e90f8--1'}

warnings = []


def sh(cmd, timeout=120, capture=True, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, shell=True, capture_output=capture, text=True, timeout=timeout, env=e)


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
    # Seed from existing v3b exports so the first run does not re-export history.
    segs = {}
    for f in sorted(os.listdir(EXPORT_DIR)):
        if f.endswith('.jsonl.gz'):
            segs[f[:-9]] = {'exported_utc': 'pre-index'}
    for s in KNOWN_BAD:
        if s not in segs:
            segs[s] = {'failed': True, 'error': 'known truncated rlog', 'exported_utc': 'pre-index'}
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


def seg_commit(seg):
    try:
        with gzip.open(f'{EXPORT_DIR}/{seg}.jsonl.gz', 'rt') as g:
            meta = json.loads(g.readline())['meta']
        return (meta.get('init') or {}).get('gitCommit', '')[:8]
    except Exception:
        return ''


def closeout_group(commit, seg):
    if seg.startswith('00000024--'):
        return 'v1_route24'
    if commit.startswith('3736edca'):
        return 'v2'
    if commit.startswith('0b8c190c'):
        return '0b8c190c_pre_tune'
    return 'baseline_pre0b8c190c'


def device_facts():
    facts = {}
    r = comma('cd /data/openpilot && git rev-parse HEAD')
    facts['head'] = r.stdout.strip() if r.returncode == 0 else None
    r = comma('cd /data/openpilot && git status --porcelain | head -50')
    facts['dirty_files'] = [l.strip() for l in r.stdout.splitlines() if l.strip()] if r.returncode == 0 else []

    # installed-state: hash each manifest target, classify vs original/candidate
    targets = {}  # path -> list of (label, entry)
    for label, mp in MANIFESTS:
        for e in json.load(open(mp))['files']:
            targets.setdefault(e['path'], []).append((label, e))
    extra = []  # (label, path, candidate)
    for label, mp in CANDIDATE_ONLY:
        for e in json.load(open(mp))['files']:
            extra.append((label, e['path'], e['candidate_sha256']))
            targets.setdefault(e['path'], [])
    paths = sorted(targets)
    r = comma('cd /data/openpilot && sha256sum ' + ' '.join(paths))
    dev = {}
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            h, _, path = line.partition('  ')
            dev[path.strip()] = h
    installed = {}
    for p in paths:
        h = dev.get(p)
        states = []
        for label, e in targets.get(p, []):
            acc = [e['candidate_sha256']] + e.get('accepted_current_sha256', [])
            if h == e['candidate_sha256']:
                states.append(f'{label}:candidate')
            elif h == e.get('original_sha256'):
                states.append(f'{label}:original')
            elif h in acc:
                states.append(f'{label}:accepted_prev')
        for label, ep, cand in extra:
            if ep == p:
                states.append(f'{label}:candidate_present' if h == cand else f'{label}:not_installed')
        if p == 'iqpilot/selfdrive/pandad/pandad':
            # binary is rebuilt at boot from pandad.cc; source hash is what matters
            states = [s for s in states if 'arming:' in s] or ['pandad:rebuilt_from_source(see pandad.cc)']
        installed[p] = {'sha256_12': h[:12] if h else None,
                        'states': states or ([f'UNKNOWN {h[:12]}'] if h else ['MISSING'])}
    facts['installed_state'] = installed
    return facts


def export_new(new_segs):
    """Run the device v3 exporter for new segs (exact names, no globs), pull results."""
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
                  + ' '.join(chunk), timeout=900)
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


def run_closeout():
    """Steering closeout over the full v3b export; returns stdout."""
    r = sh(f'/usr/bin/python3 {CLOSEOUT}', timeout=1200,
           env={'TUCSON_V3B_DIR': EXPORT_DIR})
    if r.returncode != 0:
        warnings.append('closeout failed: ' + r.stderr[-300:])
        return ''
    return r.stdout


def run_attrib():
    """long3b attribution over the full v3b export; returns parsed dict."""
    out = f'{REPORTS}/long3b_attrib_latest.json'
    r = sh(f'cd {HOME}/drives/long3 && /usr/bin/python3 {ATTRIB}', timeout=1800,
           env={'TUCSON_V3_DIR': EXPORT_DIR, 'LONG3B_OUT': out})
    if r.returncode != 0:
        warnings.append('attribute_long3b failed: ' + r.stderr[-300:])
        return {}
    try:
        return json.load(open(out))
    except Exception as e:
        warnings.append(f'attrib json unreadable: {e}')
        return {}


def closeout_for_groups(text, groups):
    """Keep table headers + rows for the requested group labels."""
    keep = []
    for line in text.splitlines():
        if line.startswith('==') or line.startswith('skipped'):
            keep.append(line)
        elif any(line.startswith(g + ' ') for g in groups):
            keep.append(line)
    return '\n'.join(keep)


def new_route_metrics(attrib, new_routes):
    """launches / stale-set engages / gas overrides restricted to new routes."""
    launches, engages, gas_n = [], [], 0
    for rt in new_routes:
        r = attrib.get(rt)
        if not r:
            continue
        for L in r['launches']:
            launches.append((rt[-2:], L['T'], L['ju_rel'], L['a_peak1s'], L['cmd_peak3s']))
        for E in r['engages']:
            if E['gap'] is not None and E['gap'] < -1.0 and E['min_acco_6s'] < -0.5:
                engages.append((rt[-2:], E['T'], E['v'], E['set_v'], E['gap'],
                                E['min_acco_6s'], E['gas_6s'], E['btn']))
        gas_n += len(r['gas'])
    return launches, engages, gas_n


def build_report(ts, new_segs, facts, closeout_txt, newest_group, attrib, new_routes, duration):
    lines = [f'# Research refresh {ts} (v3b)', '']
    if not new_segs:
        lines.append('No new data.')
        return '\n'.join(lines) + '\n'
    lines.append(f'New segments: {len(new_segs)} (approx {duration:.0f} s); new routes: {new_routes}')
    lines.append(f'Device HEAD: {facts.get("head")}; dirty files: {len(facts.get("dirty_files", []))}')
    bad = {p: s['states'] for p, s in facts.get('installed_state', {}).items()
           if any('UNKNOWN' in x or 'MISSING' in x or x.endswith(':original') for x in s['states'])}
    lines.append(f'Installed-state anomalies: {bad if bad else "none"}')
    lines.append('')
    lines.append(f'## Steering closeout — {newest_group} vs baseline')
    lines.append('```')
    lines.append(closeout_for_groups(closeout_txt, ('baseline_pre0b8c190c', newest_group)))
    lines.append('```')
    lines.append('')
    launches, engages, gas_n = new_route_metrics(attrib, new_routes)
    lines.append('## New-route longitudinal (long3b attribution)')
    lines.append(f'launches ({len(launches)}): route T ju_rel a_peak1s cmd_peak3s')
    for row in launches:
        lines.append(f'- {row}')
    lines.append(f'stale-set engages (set-v below v by >1 m/s, min_acco_6s<-0.5): {len(engages)}')
    for row in engages:
        lines.append(f'- {row}')
    lines.append(f'gas overrides on new routes: {gas_n}')
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
    ts = ts_now()
    status = {'reachable': False}
    r = comma('true', timeout=40)
    if r.returncode != 0:
        status['ts'] = ts
        os.makedirs(f'{HOURLY}/state', exist_ok=True)
        json.dump(status, open(f'{HOURLY}/state/last_status.json', 'w'))
        summary(**status, new_segments=0, new_routes=[], report_path=None,
                pushed_commit=None, installed_state=None, warnings=['comma unreachable'])
        return
    status['reachable'] = True
    st = load_state()
    try:
        inv = inventory()
    except Exception as e:
        summary(**status, error=str(e), new_segments=0, new_routes=[], report_path=None,
                pushed_commit=None, installed_state=None, warnings=[str(e)])
        return
    try:
        facts = device_facts()
    except Exception as e:
        warnings.append(f'device facts failed: {e}')
        facts = {}
    status.update(facts)
    known = set(st['segments'])
    local = {f[:-9] for f in os.listdir(EXPORT_DIR) if f.endswith('.jsonl.gz')}
    new_segs = sorted(s for s in inv if s not in known and s not in local)
    pulled, statuses = ([], {})
    if new_segs:
        pulled, statuses = export_new(new_segs)
        for s in pulled:
            st['segments'][s] = {'mtime': inv[s], 'exported_utc': ts}
        for s in new_segs:
            if s not in pulled:
                st['segments'][s] = {'mtime': inv[s], 'failed': True,
                                     'error': statuses.get(s, '')[-200:]}
                warnings.append(f'export failed (recorded, will not retry): {s}')
        save_state(st)
    report_path = None
    pushed = None
    os.makedirs(REPORTS, exist_ok=True)
    if pulled:
        new_routes = sorted({s.split('--')[0] for s in pulled})
        closeout_txt = run_closeout()
        attrib = run_attrib()
        newest = max(new_routes)
        ref_seg = next((s for s in pulled if s.startswith(newest + '--')), pulled[-1])
        newest_group = closeout_group(seg_commit(ref_seg), ref_seg)
        report = build_report(ts, pulled, facts, closeout_txt, newest_group, attrib,
                              new_routes, len(pulled) * 60.0)
        report_path = f'{REPORTS}/{ts}.md'
        open(report_path, 'w').write(report)
        if os.environ.get('REFRESH_NO_PUBLISH'):
            warnings.append('publish skipped (REFRESH_NO_PUBLISH)')
        else:
            pushed = publish(ts, report)
            mac_copy(report_path, ts)
    else:
        report_path = f'{REPORTS}/{ts}.md'
        open(report_path, 'w').write(f'# Research refresh {ts} (v3b)\n\nNo new data.\n')
        if new_segs and not pulled:
            warnings.append('new segments found but none pulled')
    json.dump({'ts': ts, 'reachable': True, 'new_segments': len(pulled)},
              open(f'{HOURLY}/state/last_status.json', 'w'))
    summary(reachable=True, new_segments=len(pulled),
            new_routes=sorted({s.split('--')[0] for s in pulled}),
            report_path=report_path, pushed_commit=pushed,
            head=facts.get('head'), installed_state=facts.get('installed_state'),
            warnings=warnings)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        summary(reachable=None, error=str(e), warnings=warnings)
