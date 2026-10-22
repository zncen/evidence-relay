"""Controlled scheduling for isolated experiments; never used by production CLI."""
import importlib.util
import os
import sys
import time
from pathlib import Path

script, mode, control, *arguments = sys.argv[1:]
spec = importlib.util.spec_from_file_location('subject', script)
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)
control = Path(control)
if mode == 'race':
    original = subject.load_ledger
    def delayed(root):
        value = original(root)
        time.sleep(.04)  # Same injected read-to-write window for both versions.
        return value
    subject.load_ledger = delayed
    (control / f'ready-{os.getpid()}').touch()
    while not (control / 'go').exists():
        time.sleep(.002)
else:
    original = subject.os.replace
    def interrupted(src, dst):
        if mode == 'after':
            original(src, dst)
        (control / 'at-replace').touch()
        while not (control / 'go').exists():
            time.sleep(.002)
        if mode == 'before':
            original(src, dst)
    subject.os.replace = interrupted
sys.argv = [script, *arguments]
raise SystemExit(subject.main())
