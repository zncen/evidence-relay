#!/usr/bin/env python3
"""One-command, stdlib-only comparison; all target data lives in TemporaryDirectory."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import platform
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BASELINE = '00b7203'


def wait_for(predicate):
    deadline = time.monotonic() + 15
    while not predicate():
        if time.monotonic() > deadline:
            raise RuntimeError('Experiment synchronization timed out')
        time.sleep(.005)


def run(script, root, *args):
    p = subprocess.run([sys.executable, str(script), '--root', str(root), *args],
                       capture_output=True, text=True, timeout=20)
    return {'exit_code': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}


def data(result):
    if result['exit_code']:
        raise RuntimeError(result)
    return json.loads(result['stdout'])


def ledger(root):
    return json.loads((root / '.evidence-relay/ledger.json').read_text())


def claim(script, root, file='a'):
    return data(run(script, root, 'claim', '--agent', 'a', '--task', 'task-a', '--files', file))['claim']['id']


def verify_args(version, cid, command):
    args = ['verify', '--agent', 'a', '--command', command]
    if version == 'improved':
        args += ['--claim-id', cid, '--require-output', 'ACCEPTED', '--timeout', '10']
    return args


def handoff_args(version, cid):
    args = ['handoff', '--agent', 'a', '--title', 'review']
    return args + (['--claim-id', cid] if version == 'improved' else [])


def stale_trials(script, version, sandbox):
    rows = []
    for scenario in ['unchanged', 'tracked-edit', 'untracked-edit', 'dotenv-edit', 'during-command', 'other-task']:
        root = sandbox / scenario
        root.mkdir()
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        target = root / ('.env' if scenario == 'dotenv-edit' else 'a')
        target.write_text('before')
        if scenario == 'tracked-edit':
            subprocess.run(['git', '-C', str(root), 'add', 'a'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@localhost',
                            'commit', '-qm', 'fixture'], check=True)
        run(script, root, 'init')
        cid = claim(script, root, target.name)
        source = 'print("ACCEPTED")'
        if scenario == 'during-command':
            source += '; from pathlib import Path; Path("a").write_text("after")'
        v = run(script, root, *verify_args(version, cid, shlex.join([sys.executable, '-c', source])))
        if scenario in ['tracked-edit', 'untracked-edit', 'dotenv-edit']:
            target.write_text('after')
        if scenario == 'other-task':
            cid = data(run(script, root, 'claim', '--agent', 'a', '--task', 'task-b', '--files', 'b'))['claim']['id']
        h = data(run(script, root, *handoff_args(version, cid)))
        note = (root / h['path']).read_text()
        accepted = (any(e['validity'] == 'current' and e['status'] == 'passed' for e in h['evidence'])
                    if version == 'improved' else '- passed:' in note)
        expected_stale = scenario != 'unchanged'
        rows.append({'version': version, 'scenario': scenario, 'expected_stale': expected_stale,
                     'accepted': accepted, 'false_negative': expected_stale and accepted,
                     'false_positive': not expected_stale and not accepted,
                     'verification': v, 'handoff': h, 'note': note})
    return rows


def race_trial(script, version, sandbox, count, same, repeat):
    root = sandbox / f'race-{count}-{same}-{repeat}'
    root.mkdir()
    control = root.parent / (root.name + '-control')
    control.mkdir()
    run(script, root, 'init')
    processes = []
    start = time.perf_counter()
    for i in range(count):
        arguments = [sys.executable, str(REPO / 'experiments/worker.py'), str(script), 'race', str(control),
                     '--root', str(root), 'claim', '--agent', f'worker-{i}', '--task', 'race',
                     '--files', 'shared' if same else f'file-{i}']
        processes.append(subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
    wait_for(lambda: len(list(control.glob('ready-*'))) == count)
    (control / 'go').touch()
    raw = []
    for p in processes:
        out, err = p.communicate(timeout=20)
        raw.append({'exit_code': p.returncode, 'stdout': out, 'stderr': err})
    elapsed = time.perf_counter() - start
    saved = ledger(root)
    successful = [json.loads(r['stdout'])['claim']['id'] for r in raw if r['exit_code'] == 0]
    persisted = {c['id'] for c in saved['claims']}
    return {'version': version, 'processes': count, 'same_file': same, 'repeat': repeat,
            'seconds': elapsed, 'successful': len(successful),
            'double_claims': max(0, len(successful) - 1) if same else 0,
            'lost_acknowledged_events': len(set(successful) - persisted),
            'unexpected_errors': sum(r['exit_code'] not in (0, 2) for r in raw),
            'raw': raw, 'ledger': saved}


def interrupt_trial(script, version, sandbox, phase):
    root = sandbox / f'interrupt-{phase}'
    root.mkdir()
    control = root.parent / (root.name + '-control')
    control.mkdir()
    run(script, root, 'init')
    initial = claim(script, root)
    p = subprocess.Popen([sys.executable, str(REPO / 'experiments/worker.py'), str(script), phase, str(control),
                          '--root', str(root), 'claim', '--agent', 'victim', '--task', 'interrupt', '--files', 'b'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    wait_for(lambda: (control / 'at-replace').exists())
    p.kill()  # Exact owned PID; no other process is targeted.
    out, err = p.communicate(timeout=5)
    before_recovery = ledger(root)
    recovery = run(script, root, 'claim', '--agent', 'recovery', '--task', 'recovery', '--files', 'c')
    after_recovery = ledger(root)
    return {'version': version, 'phase': phase, 'victim_exit': p.returncode,
            'stdout': out, 'stderr': err, 'ledger_before_recovery': before_recovery,
            'ledger_after_recovery': after_recovery, 'recovery': recovery,
            'prior_acknowledged_survives': initial in {c['id'] for c in after_recovery['claims']},
            'unacknowledged_commit_present': any(c['agent'] == 'victim' for c in before_recovery['claims'])}


def long_verify_trial(script, version, sandbox):
    root = sandbox / 'long-verify'
    root.mkdir()
    run(script, root, 'init')
    cid = claim(script, root)
    marker, gate = sandbox / 'started', sandbox / 'continue'
    source = f'import pathlib,time; pathlib.Path({str(marker)!r}).touch();\nwhile not pathlib.Path({str(gate)!r}).exists(): time.sleep(.01)\nprint("ACCEPTED")'
    p = subprocess.Popen([sys.executable, str(script), '--root', str(root),
                          *verify_args(version, cid, shlex.join([sys.executable, '-c', source]))],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    wait_for(marker.exists)
    concurrent = data(run(script, root, 'claim', '--agent', 'b', '--task', 'concurrent', '--files', 'b'))['claim']['id']
    gate.touch()
    out, err = p.communicate(timeout=15)
    saved = ledger(root)
    return {'version': version, 'lost_acknowledged_events': int(concurrent not in {c['id'] for c in saved['claims']}),
            'exit_code': p.returncode, 'stdout': out, 'stderr': err, 'ledger': saved}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=REPO / 'experiments/results/comparison.json')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    baseline = subprocess.check_output(['git', '-C', str(REPO), 'show', f'{BASELINE}:relay.py'])
    result = {'environment': {'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version, 'platform': platform.platform(),
              'cpu_count': os.cpu_count(), 'baseline_commit': subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', BASELINE], text=True).strip(),
              'checkout_commit': subprocess.check_output(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(),
              'baseline_sha256': hashlib.sha256(baseline).hexdigest(),
              'improved_sha256': hashlib.sha256((REPO / 'relay.py').read_bytes()).hexdigest(),
              'command': shlex.join([sys.executable, 'experiments/run.py', '--repeats', str(args.repeats)]),
              'harness_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), REPO / 'experiments/worker.py']},
              'race_delay_seconds': .04, 'repeats': args.repeats},
              'stale': [], 'races': [], 'interruptions': [], 'long_verify': []}
    with tempfile.TemporaryDirectory(prefix='evidence-relay-experiment-') as directory:
        base = Path(directory)
        baseline_script = base / 'baseline.py'
        baseline_script.write_bytes(baseline)
        for version, script in [('baseline', baseline_script), ('improved', REPO / 'relay.py')]:
            sandbox = base / version
            sandbox.mkdir()
            result['stale'] += stale_trials(script, version, sandbox)
            for n in [2, 4, 8]:
                for same in [False, True]:
                    for repeat in range(args.repeats):
                        result['races'].append(race_trial(script, version, sandbox, n, same, repeat))
            for phase in ['before', 'after']:
                result['interruptions'].append(interrupt_trial(script, version, sandbox, phase))
            result['long_verify'].append(long_verify_trial(script, version, sandbox))
            print(f'{version}: complete', flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(args.output)

if __name__ == '__main__':
    main()
