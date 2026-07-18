import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RELAY = Path(__file__).parents[1] / "relay.py"


class EvidenceRelayTests(unittest.TestCase):
    def run_relay(self, root, *arguments):
        return subprocess.run(
            [sys.executable, str(RELAY), "--root", str(root), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_claim_conflict_verify_and_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialized = self.run_relay(root, "init", "--project", "Demo")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)

            claimed = self.run_relay(
                root,
                "claim",
                "--agent",
                "codex",
                "--task",
                "Build parser",
                "--files",
                "relay.py",
                "tests/test_relay.py",
            )
            self.assertEqual(claimed.returncode, 0, claimed.stderr)

            conflicting = self.run_relay(
                root,
                "claim",
                "--agent",
                "claude",
                "--task",
                "Edit parser",
                "--files",
                "relay.py",
            )
            self.assertEqual(conflicting.returncode, 2)
            self.assertIn("blocked", conflicting.stdout)

            verified = self.run_relay(
                root,
                "verify",
                "--agent",
                "codex",
                "--command",
                f'{sys.executable} -c "print(42)"',
            )
            self.assertEqual(verified.returncode, 0, verified.stderr)

            handoff = self.run_relay(
                root,
                "handoff",
                "--agent",
                "codex",
                "--title",
                "Parser ready",
            )
            self.assertEqual(handoff.returncode, 0, handoff.stderr)
            ledger = json.loads((root / ".evidence-relay" / "ledger.json").read_text())
            self.assertEqual(ledger["verifications"][-1]["status"], "passed")
            self.assertEqual(len(ledger["handoffs"]), 1)
            self.assertTrue((root / ledger["handoffs"][0]["path"]).exists())


if __name__ == "__main__":
    unittest.main()
