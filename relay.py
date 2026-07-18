#!/usr/bin/env python3
"""Evidence Relay: local, evidence-first handoffs for coding agents."""

from __future__ import annotations

import argparse
import json
import os
import re
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
    stamp = datetime.now(timezone.utc).strftime("%H%M%S%f")
    return f"{prefix}_{stamp[-10:]}"


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
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


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
    normal = candidate.as_posix().lstrip("./")
    if not normal:
        raise ValueError("File path cannot be empty.")
    return normal


def git_ref(root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def active_claims(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    return [claim for claim in ledger["claims"] if claim["status"] == "active"]


def command_init(args: argparse.Namespace) -> int:
    root = root_path(args)
    target = ledger_path(root)
    if target.exists() and not args.force:
        print(f"Ledger already exists: {target}", file=sys.stderr)
        return 1
    save_ledger(root, default_ledger(args.project))
    print(f"Initialized Evidence Relay ledger at {target}")
    return 0


def command_claim(args: argparse.Namespace) -> int:
    root = root_path(args)
    ledger = load_ledger(root)
    files = sorted(set(normalize_file(path) for path in args.files))
    conflicts = []
    for claim in active_claims(ledger):
        overlap = sorted(set(files).intersection(claim["files"]))
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
    ledger = load_ledger(root)
    completed = subprocess.run(
        args.command,
        cwd=root,
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )
    output = (completed.stdout + completed.stderr).strip()[-4000:]
    verification = {
        "id": identifier("vrf"),
        "agent": args.agent,
        "command": args.command,
        "exit_code": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "output": output,
        "git_ref": git_ref(root),
        "created_at": now(),
    }
    ledger["verifications"].append(verification)
    save_ledger(root, ledger)
    print(json.dumps(verification, indent=2))
    return completed.returncode


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "handoff"


def command_handoff(args: argparse.Namespace) -> int:
    root = root_path(args)
    ledger = load_ledger(root)
    created_at = now()
    filename = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    handoff_id = identifier("hnd")
    handoff_file = root / STATE_DIR / "handoffs" / f"{filename}-{slugify(args.title)}.md"
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
    claims = active_claims(ledger)
    lines.extend(
        [f"- {claim['agent']}: {', '.join(claim['files'])}" for claim in claims]
        or ["- None"]
    )
    lines.extend(["", "## Latest verification evidence"])
    latest = ledger["verifications"][-5:]
    lines.extend(
        [
            f"- {item['status']}: {item['command']} (exit {item['exit_code']}, {item['created_at']})"
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
    verify.set_defaults(handler=command_verify)

    handoff = subparsers.add_parser("handoff", help="Export a handoff note")
    handoff.add_argument("--agent", required=True)
    handoff.add_argument("--title", required=True)
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
