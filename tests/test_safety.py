import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RELAY = Path(__file__).resolve().parents[1] / 'relay.py'

class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run_cli('init')
        self.claim = json.loads(self.run_cli('claim', '--agent', 'a', '--task', 't', '--files', 'src').stdout)['claim']['id']

    def run_cli(self, *args, code=0):
        p = subprocess.run([sys.executable, str(RELAY), '--root', str(self.root), *args], capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, code, p.stderr + p.stdout)
        return p

    def verify(self, code, *extra, expected=0):
        command = shlex.join([sys.executable, '-c', code])
        return json.loads(self.run_cli('verify', '--agent', 'a', '--claim-id', self.claim,
                                     '--command', command, *extra, code=expected).stdout)

    def test_timeout_and_output_bound(self):
        v = self.verify('import time; print("x"*100000, flush=True); time.sleep(10)', '--timeout', '.2', expected=124)
        self.assertTrue(v['timed_out'])
        self.assertTrue(v['output_truncated'])
        self.assertLessEqual(len(v['output'].encode()), 4000)

    def test_command_exit_does_not_prove_requirement(self):
        v = self.verify('print("Ran 0 tests")', '--require-output', 'Ran 5 tests', expected=1)
        self.assertEqual(v['status'], 'requirements_unmet')

    def test_change_during_verify_is_invalid(self):
        v = self.verify('from pathlib import Path; Path("new").write_text("changed")', expected=1)
        self.assertFalse(v['stable'])
        h = json.loads(self.run_cli('handoff', '--agent', 'a', '--claim-id', self.claim, '--title', 't').stdout)
        self.assertEqual(h['evidence'][0]['validity'], 'stale')

    def test_scope_ownership_and_directory_conflict(self):
        self.run_cli('claim', '--agent', 'b', '--task', 'u', '--files', 'src/file', code=2)
        self.run_cli('verify', '--agent', 'b', '--claim-id', self.claim, '--command', 'true', code=1)
        other = json.loads(self.run_cli('claim', '--agent', 'a', '--task', 'u', '--files', 'other').stdout)['claim']['id']
        self.verify('print("ok")')
        h = json.loads(self.run_cli('handoff', '--agent', 'a', '--claim-id', other, '--title', 'u').stdout)
        self.assertEqual(h['evidence'], [])
        self.run_cli('release', self.claim)
        self.run_cli('handoff', '--agent', 'a', '--claim-id', self.claim, '--title', 't', code=1)

    def test_parallel_claims_no_loss_or_double_owner(self):
        for same in (False, True):
            processes = [subprocess.Popen([sys.executable, str(RELAY), '--root', str(self.root), 'claim',
                         '--agent', f'b{i}', '--task', 'parallel', '--files', 'shared' if same else f'f{i}'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(8)]
            outcomes = [p.communicate(timeout=10) for p in processes]
            self.assertTrue(all(p.returncode in (0, 2) for p in processes), outcomes)
            successes = [json.loads(out[0])['claim']['id'] for p, out in zip(processes, outcomes) if p.returncode == 0]
            ledger = json.loads((self.root / '.evidence-relay/ledger.json').read_text())
            self.assertTrue(set(successes) <= {c['id'] for c in ledger['claims']})
            self.assertEqual(len(successes), 1 if same else 8)

    def test_long_verify_does_not_overwrite_new_claim(self):
        marker = self.root.parent / (self.root.name + '-started')
        gate = self.root.parent / (self.root.name + '-go')
        self.addCleanup(lambda: marker.unlink(missing_ok=True))
        self.addCleanup(lambda: gate.unlink(missing_ok=True))
        code = f'import pathlib,time; pathlib.Path({str(marker)!r}).touch();\nwhile not pathlib.Path({str(gate)!r}).exists(): time.sleep(.01)'
        proc = subprocess.Popen([sys.executable, str(RELAY), '--root', str(self.root), 'verify', '--agent', 'a',
                                 '--claim-id', self.claim, '--command', shlex.join([sys.executable, '-c', code])],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(marker.exists())
            c = json.loads(self.run_cli('claim', '--agent', 'b', '--task', 'u', '--files', 'z').stdout)['claim']['id']
            gate.touch()
            out, err = proc.communicate(timeout=5)
            self.assertEqual(proc.returncode, 0, err + out)
            ledger = json.loads((self.root / '.evidence-relay/ledger.json').read_text())
            self.assertIn(c, [c['id'] for c in ledger['claims']])
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
