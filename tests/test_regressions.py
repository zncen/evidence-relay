import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RELAY = Path(__file__).resolve().parents[1] / 'relay.py'
spec = importlib.util.spec_from_file_location('relay', RELAY)
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)

class RegressionTests(unittest.TestCase):
    def test_dotenv_is_preserved(self):
        self.assertEqual(relay.normalize_file('./.env'), '.env')

    def test_stale_evidence_and_command_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            def run(*a):
                p = subprocess.run([sys.executable, str(RELAY), '--root', d, *a], capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stderr)
                return p.stdout
            run('init')
            (root / '.env').write_text('fixture=1')
            c = json.loads(run('claim', '--agent', 'a', '--task', 't', '--files', '.env'))['claim']
            v = json.loads(run('verify', '--agent', 'a', '--claim-id', c['id'], '--command', 'true'))
            self.assertEqual(v['status'], 'command_succeeded')
            (root / '.env').write_text('fixture=2')
            h = json.loads(run('handoff', '--agent', 'a', '--claim-id', c['id'], '--title', 't'))
            self.assertEqual(h['evidence'][0]['validity'], 'stale')

    def test_snapshot_includes_untracked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'new').write_text('one')
            before = relay.snapshot(root)
            (root / 'new').write_text('two')
            self.assertNotEqual(before, relay.snapshot(root))

    def test_snapshot_tracks_modes_deletion_and_symlink_without_following(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as outside:
            root = Path(d)
            external = Path(outside) / 'external'
            external.write_text('external fixture')
            (root / 'link').symlink_to(external)
            first = relay.snapshot(root)
            external.write_text('external changed')
            self.assertEqual(first, relay.snapshot(root))  # Explicit external-dependency limit.
            (root / 'link').unlink()
            self.assertNotEqual(first, relay.snapshot(root))
            file = root / 'local'
            file.write_text('fixture')
            first = relay.snapshot(root)
            file.chmod(0o700)
            self.assertNotEqual(first, relay.snapshot(root))
