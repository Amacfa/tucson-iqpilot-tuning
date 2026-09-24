#!/usr/bin/env python3
"""Version-pinned warning and F1B restoration package. Default is check-only; never restarts services."""
from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile, time, datetime
ROOT = Path('/data/openpilot')
HERE = Path(__file__).resolve().parent

def require(condition, message='Validation failed'):
    if not condition:
        raise RuntimeError(message)

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

PANDAD_BINARY = 'iqpilot/selfdrive/pandad/pandad'
PANDAD_SOURCE = 'iqpilot/selfdrive/pandad/pandad.cc'
TUNE_CARCONTROLLER_REL = '.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carcontroller.py'
TUNE_CARCONTROLLER_FALLBACK = 'a8cf776cefaa8e5cf54621165df58404fa1f85ccece36f9ab11e4274737af7a5'
TUNE_CONTROLLER_REL = 'iqpilot/selfdrive/controls/lib/latcontrol_torque.py'
TUNE_CONTROLLER_FALLBACK = 'bb3f78b19a33bff24b05a4723aa5cca754d46c2bde18a6d030a4cff6165aa9bf'

def tune_candidate_hashes():
    """Candidate hashes of tune-package files, from a sibling tune-*/package manifest if present."""
    out = {TUNE_CARCONTROLLER_REL: TUNE_CARCONTROLLER_FALLBACK, TUNE_CONTROLLER_REL: TUNE_CONTROLLER_FALLBACK}
    for sibling in HERE.parent.glob('tune-*/package/manifest.json'):
        try:
            tm = json.loads(sibling.read_text())
            for e in tm['files']:
                if e['path'] in out:
                    out[e['path']] = e['candidate_sha256']
        except Exception:
            pass
    return out

def checked_files(root, manifest, direction):
    expected = 'original_sha256' if direction == 'apply' else 'candidate_sha256'
    for ent in manifest['files']:
        rel = Path(ent['path'])
        require(not rel.is_absolute() and '..' not in rel.parts, 'Validation failed')
        target = root / rel
        current = digest(target)
        allowed = {ent[expected]} if direction == 'apply' else {ent['original_sha256'], ent['candidate_sha256']}
        # The boot build (iqpilot/system/manager/build.py) recompiles pandad from
        # pandad.cc, so the on-device binary legitimately carries a third hash.
        if rel != Path(PANDAD_BINARY):
            require(current in allowed, f'Unexpected current bytes: {rel}')
        sub = 'candidate' if direction == 'apply' else 'rollback'
        src = HERE / sub / rel
        new = 'candidate_sha256' if direction == 'apply' else 'original_sha256'
        require(digest(src) == ent[new], f'Package checksum mismatch: {rel}')
        if rel.suffix == '.py':
            compile(src.read_bytes(), str(rel), 'exec')

def parked():
    sys.path.insert(0, str(ROOT))
    from iqpilot.cereal import messaging
    from iqpilot.common.params import Params
    p = Params()
    sm = messaging.SubMaster(['deviceState', 'pandaStates', 'managerState'])
    end = time.monotonic() + 2.2
    while time.monotonic() < end:
        sm.update(100)
    require(all((time.monotonic() - sm.recv_time[s] < 2.1 for s in ['deviceState', 'pandaStates', 'managerState'])), 'Fresh parked status unavailable')
    require(all((sm.valid[x] for x in ['deviceState', 'pandaStates', 'managerState'])), 'Parked telemetry is invalid')
    require(not p.get_bool('IsOnroad') and (not sm['deviceState'].started), 'Vehicle is onroad')
    require(len(sm['pandaStates']) == 1 and all((not (x.ignitionLine or x.ignitionCan or x.controlsAllowed) for x in sm['pandaStates'])), 'Ignition/controls must be off')
    require(not any((x.running for x in sm['managerState'].processes if x.name in ['card', 'controlsd'])), 'Driving processes running')
    return p

def transaction(root, manifest, direction, backup):
    """Atomic file replacement; restore every replaced file if any step fails."""
    backup.mkdir(parents=True, exist_ok=False)
    staged = []
    replaced = []
    try:
        for ent in manifest['files']:
            rel = Path(ent['path'])
            target = root / rel
            old = backup / rel
            old.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, old)
            source = HERE / ('candidate' if direction == 'apply' else 'rollback') / rel
            fd, name = tempfile.mkstemp(prefix='.iq-warning-', dir=target.parent)
            staged.append((Path(name), target, old))
            with os.fdopen(fd, 'wb') as f:
                f.write(source.read_bytes())
                f.flush()
                os.fsync(f.fileno())
            os.chmod(name, ent['mode'])
        for tmp, target, old in staged:
            os.replace(tmp, target)
            replaced.append((target, old))
        for ent in manifest['files']:
            expected = ent['candidate_sha256' if direction == 'apply' else 'original_sha256']
            require(digest(root / ent['path']) == expected, 'Post-write verification failed')
        receipt = {'direction': direction, 'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'manifest_sha256': digest(HERE / 'manifest.json'), 'files': manifest['files'], 'services_restarted': False}
        (backup / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    except BaseException:
        for target, old in reversed(replaced):
            fd, name = tempfile.mkstemp(prefix='.iq-warning-restore-', dir=target.parent)
            os.close(fd)
            shutil.copy2(old, name)
            os.replace(name, target)
        raise
    finally:
        for tmp, _, _ in staged:
            tmp.unlink(missing_ok=True)
    return receipt

def call_order_positions(objdump_text):
    safety = state = None
    for line in objdump_text.splitlines():
        if 'bl' not in line or ':' not in line:
            continue
        head = line.split(':')[0].strip()
        if not head or not all(c in '0123456789abcdefABCDEF' for c in head):
            continue
        addr = int(head, 16)
        if safety is None and 'configureSafetyMode' in line:
            safety = addr
        elif state is None and 'process_panda_state' in line:
            state = addr
    return safety, state

def pandad_candidate_call_order(exe):
    out = subprocess.check_output(['objdump', '-d', '-C', exe], text=True, errors='replace')
    safety, state = call_order_positions(out)
    return safety is not None and state is not None and safety < state

def supported_configuration(p, manifest, installed=False):
    for key, expected in manifest['required_params'].items():
        value = p.get_bool(key) if isinstance(expected, bool) else p.get(key, return_default=True)
        require(value == expected, f'Unsupported setting: {key}={value!r}, expected {expected!r}')
    extra_allowed = {}
    if installed:
        extra_allowed[TUNE_CARCONTROLLER_REL] = {tune_candidate_hashes()[TUNE_CARCONTROLLER_REL]}
    for rel, expected_hash in manifest.get('validation_dependencies', {}).items():
        allowed = {expected_hash} | extra_allowed.get(rel, set())
        require(digest(ROOT / rel) in allowed, f'Validated dependency changed: {rel}')
    require(not Path('/data/safe_staging/finalized/.overlay_consistent').exists(), 'An IQ update is staged; install and revalidate that version first')
    import importlib.util
    origin = importlib.util.find_spec('iqdbc.car.hyundai.carstate').origin
    require(Path(origin).resolve() == (ROOT / '.venv/lib/python3.12/site-packages/iqdbc/car/hyundai/carstate.py').resolve(), 'Unexpected imported iqdbc location')
    from iqpilot.cereal import car, custom, messaging
    cp = messaging.log_from_bytes(p.get('CarParamsPersistent'), car.CarParams)
    require(cp.carFingerprint == 'HYUNDAI_TUCSON_4TH_GEN' and cp.flags == 8206 and cp.openpilotLongitudinalControl, 'Validation failed')
    require(cp.extFlags == 132 and cp.steerControlType == car.CarParams.SteerControlType.torque, 'Unsupported vehicle control mode')
    cp_iq = messaging.log_from_bytes(p.get('IQCarParamsPersistentV2'), custom.IQCarParams)
    require(cp_iq.flags == 4 and cp_iq.iqSafetyFlags == 32, 'Unsupported IQ vehicle safety flags')
    require(cp.alternativeExperience == 1024 and len(cp.safetyConfigs) == 1 and (cp.safetyConfigs[0].safetyParam == 44) and str(cp.safetyConfigs[0].safetyModel) == 'hyundaiCanfd', 'Validation failed')
    controller_allowed = {manifest['candidate_controller_sha256' if installed else 'torque_controller_sha256']}
    if installed:
        # The tune package legitimately replaces this file after the arming package.
        controller_allowed.add(tune_candidate_hashes()[TUNE_CONTROLLER_REL])
    require(digest(ROOT / TUNE_CONTROLLER_REL) in controller_allowed, 'Torque controller changed; revalidate package')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    op = ap.add_mutually_exclusive_group()
    op.add_argument('--apply', action='store_true')
    op.add_argument('--rollback', action='store_true')
    op.add_argument('--check', action='store_true')
    op.add_argument('--verify-installed', action='store_true', help='Read-only post-restart source and running-executable verification')
    args = ap.parse_args()
    manifest = json.loads((HERE / 'manifest.json').read_text())
    direction = 'rollback' if (args.rollback or args.verify_installed) else 'apply'
    require(manifest['software_validation_passed'], 'Package validation is incomplete')
    require(subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip() == manifest['head'], 'IQ version changed; package requires revalidation')
    p = parked()
    if direction == 'apply' or args.verify_installed:
        supported_configuration(p, manifest, installed=args.verify_installed)
    checked_files(ROOT, manifest, direction)
    if args.verify_installed:
        for ent in manifest['files']:
            if ent['path'] == PANDAD_BINARY:
                continue
            require(digest(ROOT / ent['path']) == ent['candidate_sha256'], f'Candidate is not fully installed: {ent["path"]}')
        expected_cc = next(e['candidate_sha256'] for e in manifest['files'] if e['path'] == PANDAD_SOURCE)
        require(digest(ROOT / PANDAD_SOURCE) == expected_cc, 'pandad.cc is not at the candidate hash')
        run = subprocess.run(['pgrep', '-x', 'pandad'], capture_output=True, text=True)
        pids = run.stdout.split()
        require(run.returncode == 0 and len(pids) == 1 and pids[0].isdigit(), 'Expected one running pandad process')
        exe = str(Path('/proc') / pids[0] / 'exe')
        require(pandad_candidate_call_order(exe), 'Running pandad does not show candidate safety/publish call order; stop and inspect before ignition')
        print(json.dumps({'installed_and_running_verified': True, 'changes_made': False, 'physical_test_pending': True,
                          'pandad_verified_by': 'candidate source hash + disassembled call order'}))
        return
    if not (args.apply or args.rollback):
        print(json.dumps({'check_passed': True, 'changes_made': False, 'head': manifest['head']}))
        return
    p = parked()
    require(subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip() == manifest['head'], 'IQ version changed during preflight')
    if direction == 'apply':
        supported_configuration(p, manifest)
    checked_files(ROOT, manifest, direction)
    backup = Path('/data/iq-warning-backups') / (datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ') + '-' + direction)
    receipt = transaction(ROOT, manifest, direction, backup)
    print(json.dumps({'completed': direction, 'backup': str(backup), 'services_restarted': False, 'next': 'Supervised parked restart and startup-log verification required; do not claim dashboard fix from installation alone.'}))
if __name__ == '__main__':
    main()
