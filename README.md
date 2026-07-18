# Evidence Relay

Evidence Relay is a local-first coordination ledger for teams of coding agents.
It makes three handoff facts inspectable:

1. Which agent owns which files right now.
2. Which command actually verified a change, with the exit code and captured output.
3. What the next operator needs to review.

The project includes a zero-dependency Python CLI and a static dashboard that
renders a fictional ledger. It never uploads a project ledger.

## Why it exists

Multi-agent work often fails at the seams: two agents edit the same file,
a passing test is reported without evidence, or an important decision disappears
in a chat window. Evidence Relay creates a small, portable audit trail before
the next handoff.

## Quick start

~~~bash
git clone <your-public-repository-url>
cd evidence-relay
python3 -m unittest discover -s tests -v

# Try the CLI in a disposable folder so the repository itself stays clean.
mkdir -p /tmp/relay-playground
python3 relay.py --root /tmp/relay-playground init --project "My agent project"
python3 relay.py --root /tmp/relay-playground claim \
  --agent codex \
  --task "Implement parser" \
  --files relay.py tests/test_relay.py
python3 relay.py --root /tmp/relay-playground verify \
  --agent codex \
  --command "python3 -m unittest discover -s tests -v"
python3 relay.py --root /tmp/relay-playground handoff \
  --agent codex \
  --title "Parser ready for review"
python3 relay.py --root /tmp/relay-playground status
~~~

The local ledger lives in the .evidence-relay directory, which is intentionally
ignored by Git because it may contain project-specific command output.

## Dashboard

Serve this directory from the repository root:

~~~bash
python3 -m http.server 8000
~~~

Then open localhost on port 8000 followed by /dashboard/. The page loads the
demo ledger, or you can use Open ledger to view a local JSON ledger without
uploading it.

The dashboard command palette is available from the Command button or
Cmd/Ctrl + K. It supports arrow-key selection, Enter to run, and Escape or a
backdrop click to close.

## CLI commands

| Command | Result |
| --- | --- |
| init | Creates an atomic JSON ledger. |
| claim | Records file boundaries and returns exit code 2 on overlap. |
| release | Marks a claim released. |
| verify | Runs a command and stores its exit code, output, timestamp, and Git reference. |
| handoff | Writes a Markdown handoff containing active boundaries and recent proof. |
| status | Prints the current relay state as JSON. |

## OpenAI Build Week submission notes

Evidence Relay was created as a new Developer Tools submission for OpenAI Build
Week. The intended build workflow is Codex with GPT-5.6: use Codex to implement
and test the CLI/dashboard, then retain the relevant Codex feedback-session ID
in the Devpost submission before final submission.

For the final Devpost form:

- Record a public demo video under three minutes using DEMO.md.
- Publish this repository under the included MIT license, or share a private
  repository with the reviewers specified in the competition rules.
- Add the actual /feedback session ID from the GPT-5.6 Codex build session.
- Describe only the work created during the competition period.

The demo ledger is fictional. No existing customer data, personal data, or
private collaboration memory is included in this repository.
