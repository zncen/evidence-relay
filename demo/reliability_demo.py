#!/usr/bin/env python3
"""A disposable demonstration; writes only to its own TemporaryDirectory."""
import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

relay = Path(__file__).resolve().parents[1] / 'relay.py'
with tempfile.TemporaryDirectory(prefix='relay-demo-') as directory:
    root = Path(directory)
    def run(*args):
        result = subprocess.run([sys.executable, str(relay), '--root', directory, *args], capture_output=True, text=True, check=True)
        print(result.stdout)
        return result.stdout
    (root / 'answer.py').write_text('answer = 42\n')
    run('init', '--project', 'Evidence freshness demo')
    cid = json.loads(run('claim', '--agent', 'demo', '--task', 'answer correctness', '--files', 'answer.py'))['claim']['id']
    command = shlex.join([sys.executable, '-c', 'from answer import answer; assert answer == 42; print("ASSERTION_OK")'])
    run('verify', '--agent', 'demo', '--claim-id', cid, '--command', command, '--require-output', 'ASSERTION_OK')
    def handoff():
        h = json.loads(run('handoff', '--agent', 'demo', '--claim-id', cid, '--title', 'Answer review'))
        print((root / h['path']).read_text())
    print('=== 未改檔：current / passed ===')
    handoff()
    (root / 'answer.py').write_text('answer = 0\n')
    print('=== 改檔後：stale / passed（歷史退出成功，已過期）===')
    handoff()
