#!/usr/bin/env python3
"""Evidence Relay: local, evidence-first handoffs for coding agents."""

from __future__ import annotations

import argparse
import fcntl
import functools
import hashlib
import json
import os
import re
import selectors
import signal
import time
import tempfile
import uuid
from contextlib import contextmanager
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_DIR = ".evidence-relay"
LEDGER_NAME = "ledger.json"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def identifier(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def root_path(args: argparse.Namespace) -> Path:
    return Path(args.root).resolve()


def ledger_path(root: Path) -> Path:
    return root / STATE_DIR / LEDGER_NAME


def default_ledger(project: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project": {"name": project, "created_at": now()},
        "claims": [],
        "verifications": [],
        "handoffs": [],
    }


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="ledger-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextmanager
def transaction(root):
    state = root / STATE_DIR
    state.mkdir(parents=True, exist_ok=True)
    with (state / "ledger.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def serialized(fn):
    @functools.wraps(fn)
    def wrapped(args):
        with transaction(root_path(args)):
            return fn(args)
    return wrapped


def snapshot(root):
    """Hash every regular file and symlink, including untracked/ignored files.

    Only ledger internals, Git internals and Python cache directories are excluded.
    Symlinks are hashed as links and never followed outside the project.
    """
    digest = hashlib.sha256()
    def fail_walk(error):
        raise error

    for directory, dirs, files in os.walk(root, followlinks=False, onerror=fail_walk):
        dirs[:] = sorted(d for d in dirs if d not in {STATE_DIR, ".git", "__pycache__"})
        links = [d for d in dirs if (Path(directory) / d).is_symlink()]
        dirs[:] = [d for d in dirs if d not in links]
        for name in sorted(files + links):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative == ".git":
                continue
            item = hashlib.sha256()
            if path.is_symlink():
                kind = "link"
                item.update(os.readlink(path).encode())
            elif path.is_file():
                kind = "file:" + str(path.stat().st_mode & 0o777)
                with path.open("rb") as stream:
                    for block in iter(lambda: stream.read(65536), b""):
                        item.update(block)
            else:
                raise ValueError(f"Unsupported snapshot entry: {relative}")
            digest.update(json.dumps([relative, kind, item.hexdigest()]).encode())
    return digest.hexdigest()


def selected_claim(ledger, args):
    claim = next((c for c in active_claims(ledger)
                  if c["id"] == args.claim_id and c["agent"] == args.agent), None)
    if claim is None:
        raise ValueError("An active claim owned by this agent is required.")
    return claim


def run_bounded(command, root, timeout):
    if not 0 < timeout <= 86400:
        raise ValueError("Timeout must be between 0 and 86400 seconds.")
    process = subprocess.Popen(command, cwd=root, shell=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    tail = b""
    total = 0
    timed_out = False
    deadline = time.monotonic() + timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            for key, _ in selector.select(min(remaining, 0.1)):
                block = os.read(key.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(key.fileobj)
                else:
                    total += len(block)
                    tail = (tail + block)[-4000:]
        if not timed_out:
            try:
                process.wait(timeout=max(0.001, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                timed_out = True
    finally:
        # Own process group only; also close surviving child writers after success.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        selector.close()
        process.stdout.close()
    return (124 if timed_out else process.returncode), tail.decode("utf-8", "replace"), timed_out, total > 4000


def load_ledger(root: Path) -> dict[str, Any]:
    path = ledger_path(root)
    if not path.exists():
        raise FileNotFoundError(
            f"No ledger found at {path}. Run 'relay.py init' in the project first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def save_ledger(root: Path, ledger: dict[str, Any]) -> None:
    write_json_atomic(ledger_path(root), ledger)


def normalize_file(value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"File must be a project-relative path: {value}")
    normal = candidate.as_posix()
    if normal == ".":
        raise ValueError("File path cannot be empty.")
    return normal


def git_ref(root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=5,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def active_claims(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    return [claim for claim in ledger["claims"] if claim["status"] == "active"]


@serialized
def command_init(args: argparse.Namespace) -> int:
    root = root_path(args)
    target = ledger_path(root)
    if target.exists() and not args.force:
        print(f"Ledger already exists: {target}", file=sys.stderr)
        return 1
    save_ledger(root, default_ledger(args.project))
    print(f"Initialized Evidence Relay ledger at {target}")
    return 0


@serialized
def command_claim(args: argparse.Namespace) -> int:
    root = root_path(args)
    ledger = load_ledger(root)
    files = sorted(set(normalize_file(path) for path in args.files))
    conflicts = []
    for claim in active_claims(ledger):
        overlap = sorted(
            a for a in files
            if any(a == b or a.startswith(b + "/") or b.startswith(a + "/")
                   for b in claim["files"])
        )
        if overlap:
            conflicts.append({"claim_id": claim["id"], "agent": claim["agent"], "files": overlap})
    if conflicts:
        print(json.dumps({"status": "blocked", "conflicts": conflicts}, indent=2))
        return 2
    claim = {
        "id": identifier("clm"),
        "agent": args.agent,
        "task": args.task,
        "files": files,
        "status": "active",
        "created_at": now(),
        "released_at": None,
    }
    ledger["claims"].append(claim)
    save_ledger(root, ledger)
    print(json.dumps({"status": "claimed", "claim": claim}, indent=2))
    return 0


@serialized
def command_release(args: argparse.Namespace) -> int:
    root = root_path(args)
    ledger = load_ledger(root)
    claim = next((item for item in ledger["claims"] if item["id"] == args.claim_id), None)
    if claim is None:
        print(f"Unknown claim: {args.claim_id}", file=sys.stderr)
        return 1
    claim["status"] = "released"
    claim["released_at"] = now()
    save_ledger(root, ledger)
    print(f"Released {args.claim_id}")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    root = root_path(args)
    with transaction(root):
        ledger = load_ledger(root)
        claim = dict(selected_claim(ledger, args))
        before = snapshot(root)
    code, output, timed_out, truncated = run_bounded(args.command, root, args.timeout)
    with transaction(root):
        ledger = load_ledger(root)  # Never save the pre-command ledger.
        after = snapshot(root)
        current = next((c for c in active_claims(ledger) if c == claim), None)
        stable = before == after and current is not None
        status = ("timed_out" if timed_out else "failed" if code else
                  "passed" if args.require_output and args.require_output in output else
                  "requirements_unmet" if args.require_output else "command_succeeded")
        verification = {
            "id": identifier("vrf"), "agent": args.agent,
            "claim_id": claim["id"], "task": claim["task"], "files": claim["files"],
            "command": args.command, "exit_code": code, "status": status,
            "require_output": args.require_output, "output": output,
            "output_truncated": truncated, "timed_out": timed_out,
            "snapshot_before": before, "snapshot_after": after,
            "stable": stable, "git_ref": git_ref(root), "created_at": now(),
        }
        ledger["verifications"].append(verification)
        save_ledger(root, ledger)
    print(json.dumps(verification, indent=2))
    return code if code > 0 else (1 if code < 0 or not stable or status == "requirements_unmet" else 0)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "handoff"


@serialized
def command_handoff(args: argparse.Namespace) -> int:
    root = root_path(args)
    ledger = load_ledger(root)
    created_at = now()
    filename = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    handoff_id = identifier("hnd")
    handoff_file = root / STATE_DIR / "handoffs" / f"{filename}-{handoff_id}-{slugify(args.title)}.md"
    lines = [
        f"# {args.title}",
        "",
        f"- Handoff ID: {handoff_id}",
        f"- Prepared by: {args.agent}",
        f"- Created: {created_at}",
        f"- Git ref: {git_ref(root) or 'uncommitted'}",
        "",
        "## Active file boundaries",
    ]
    claim = selected_claim(ledger, args)
    claims = [claim]
    lines.extend(
        [f"- {claim['agent']}: {', '.join(claim['files'])}" for claim in claims]
        or ["- None"]
    )
    lines.extend(["", "## Latest verification evidence"])
    current_snapshot = snapshot(root)
    latest = [dict(item) for item in ledger["verifications"] if item.get("claim_id") == claim["id"]]
    for item in latest:
        item["validity"] = ("current" if item.get("stable") and
                            item.get("snapshot_after") == current_snapshot and
                            item.get("task") == claim["task"] and item.get("files") == claim["files"]
                            else "stale")
    lines.extend(
        [
            f"- {item['validity']} / {item['status']}: {item['command']} (exit {item['exit_code']}, {item['created_at']})"
            for item in latest
        ]
        or ["- No verification recorded yet."]
    )
    lines.extend(["", "## Next operator", "- Review active boundaries before changing files."])
    handoff_file.parent.mkdir(parents=True, exist_ok=True)
    handoff_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    record = {
        "id": handoff_id,
        "agent": args.agent,
        "title": args.title,
        "claim_id": claim["id"],
        "evidence": [{"id": i["id"], "validity": i["validity"], "status": i["status"]} for i in latest],
        "path": handoff_file.relative_to(root).as_posix(),
        "created_at": created_at,
    }
    ledger["handoffs"].append(record)
    save_ledger(root, ledger)
    print(json.dumps(record, indent=2))
    return 0


def command_status(args: argparse.Namespace) -> int:
    ledger = load_ledger(root_path(args))
    summary = {
        "project": ledger["project"],
        "active_claims": active_claims(ledger),
        "latest_verification": ledger["verifications"][-1] if ledger["verifications"] else None,
        "handoffs": ledger["handoffs"][-3:],
    }
    print(json.dumps(summary, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--root", default=".", help="Project directory (default: current directory)")
    subparsers = root.add_subparsers(dest="subcommand", required=True)

    init = subparsers.add_parser("init", help="Create a local evidence ledger")
    init.add_argument("--project", default="Untitled project")
    init.add_argument("--force", action="store_true")
    init.set_defaults(handler=command_init)

    claim = subparsers.add_parser("claim", help="Claim file boundaries")
    claim.add_argument("--agent", required=True)
    claim.add_argument("--task", required=True)
    claim.add_argument("--files", nargs="+", required=True)
    claim.set_defaults(handler=command_claim)

    release = subparsers.add_parser("release", help="Release a claim")
    release.add_argument("claim_id")
    release.set_defaults(handler=command_release)

    verify = subparsers.add_parser("verify", help="Run and retain test evidence")
    verify.add_argument("--agent", required=True)
    verify.add_argument("--command", required=True)
    verify.add_argument("--claim-id", required=True)
    verify.add_argument("--timeout", type=float, default=300)
    verify.add_argument("--require-output", help="Required literal in retained output; explicit acceptance criterion")
    verify.set_defaults(handler=command_verify)

    handoff = subparsers.add_parser("handoff", help="Export a handoff note")
    handoff.add_argument("--agent", required=True)
    handoff.add_argument("--title", required=True)
    handoff.add_argument("--claim-id", required=True)
    handoff.set_defaults(handler=command_handoff)

    status = subparsers.add_parser("status", help="Show active boundaries and evidence")
    status.set_defaults(handler=command_status)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except (FileNotFoundError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
