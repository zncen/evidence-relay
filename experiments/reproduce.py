#!/usr/bin/env python3
"""Run all tests and isolated comparisons; retain new results separately."""
import argparse
import subprocess
import sys
from pathlib import Path
from summarize import summarize

repo = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=repo / 'experiments/results/reproduced')
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
with (args.output / 'tests.txt').open('w') as output:
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=repo,
                           stdout=output, stderr=subprocess.STDOUT)
if tests.returncode:
    raise SystemExit(f'Tests failed; see {args.output / "tests.txt"}')
subprocess.run([sys.executable, str(repo / 'experiments/run.py'), '--output', str(args.output / 'comparison.json')], check=True)
(args.output / 'summary.md').write_text(summarize(args.output / 'comparison.json'))
print(f'Tests and comparison complete: {args.output}')
