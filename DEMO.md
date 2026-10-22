> 2026-10-22 更新：以下保留原始競賽展示構想；新版本 verify/handoff 需要 --claim-id。可靠性展示請執行 `python3 demo/reliability_demo.py`，步驟與限制見 README.md。

# Evidence Relay — 2 minute 20 second demo script

## 0:00–0:18 — Problem

“Coding agents move quickly, but collaboration evidence gets lost. Two agents
can edit one file, a test result can be asserted without proof, and the next
operator has to reconstruct context from chat.”

Show the dashboard with the fictional demo ledger.

## 0:18–0:52 — Claim a boundary

Run:

~~~bash
python3 relay.py --root /tmp/relay-demo init --project "Release candidate"
python3 relay.py --root /tmp/relay-demo claim --agent codex \
  --task "Build parser" --files relay.py tests/test_relay.py
python3 relay.py --root /tmp/relay-demo claim --agent claude \
  --task "Edit parser" --files relay.py
~~~

Point out that the second command returns exit code 2 and identifies the
existing owner. The tool protects a file boundary without a central service.

## 0:52–1:22 — Keep verification proof

Run:

~~~bash
python3 relay.py --root /tmp/relay-demo verify --agent codex \
  --command "python3 -c \"print('parser tests passed')\""
~~~

Show that Evidence Relay retains the exact command, output, exit code,
timestamp, and Git reference rather than only a conversational claim.

## 1:22–1:50 — Export the handoff

Run:

~~~bash
python3 relay.py --root /tmp/relay-demo handoff --agent codex \
  --title "Parser ready for review"
python3 relay.py --root /tmp/relay-demo status
~~~

Open the generated Markdown note. It contains the active boundaries and latest
verification so the next coding agent can review the work before touching it.

## 1:50–2:12 — Dashboard

Open the dashboard, click Simulate collision, then use Command or Cmd/Ctrl + K.
Arrow to Export latest handoff and press Enter.

Emphasize that the dashboard is a local JSON viewer: it makes a handoff easy to
inspect without uploading an engineering ledger.

## 2:12–2:20 — OpenAI/Codex contribution

“I built Evidence Relay with Codex and GPT-5.6 during OpenAI Build Week. Codex
helped turn a real multi-agent coordination problem into a tested local CLI,
an auditable ledger format, and this interactive demo. The submission will
include the corresponding Codex feedback-session ID.”

Replace that last sentence with the actual verified session details before
recording and submitting.
