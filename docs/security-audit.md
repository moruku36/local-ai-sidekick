# Local security audit candidate

[Documentation index](README.md) | [Current status](current-status.md)

This candidate brings the public, offline security log pipeline from
[`home-ai-engineering-lab`](https://github.com/moruku36/home-ai-engineering-lab/tree/e529c702ab7dcd74285d72a5991b5553c50d23a3)
into Sidekick. The source pipeline and schema are adapted from that repository's
`scripts/security_log_pipeline.py` and `schemas/security-analysis-event.schema.json`;
its synthetic tests are carried into `tests/test_security_audit.py`. The Lab
repository is unchanged. This creates a reviewable migration candidate, not an
operational cutover. The Lab's NUC ingestion, n8n workflow, Compose proposal,
network bridge and production scheduling remain separate and inactive here.

## Offline example

From this repository root, with Python 3.10+:

```powershell
$env:PYTHONPATH='src'
python -m sidekick.security_audit --input tests/fixtures/security_audit/synthetic-auth.txt --source sshd --bsd-year 2026 --synthetic-or-public
```

On Bash use `PYTHONPATH=src python -m sidekick.security_audit ...`. Installed
packages also provide `sidekick-security-audit` with the same flags. JSON is
printed to stdout. Redirect it only to a protected local path if persistence
is desired; do not commit reports. No OS command, remediation, service control,
Git mutation or external AI call is performed by this command.

To opt in to an **already running**, loopback-bound Ollama service and an
**already installed** model, add `--ollama --model <installed-model-name>`.
No model is pulled. The audit endpoint is fixed at `127.0.0.1:11434`, and the
client does not support a remote URL, proxy or redirect. The model receives
only bounded, redacted log entries. Each proposed finding must pass schema and
exact evidence checks; accepted model findings remain **unverified human-review
suggestions**. An unavailable Ollama returns `DEFERRED_LLM` with the rule-only
findings. This opt-in path has not been exercised against a live model here.

The CLI requires `--synthetic-or-public`. It is a user assertion, **not a data
classification or complete de-identification guarantee**. The source
redactor covers common tokens, passwords, private keys, email and private IP
patterns, but cannot identify every secret or personal detail. Do not supply
real logs, private code, incident material or confidential documents. Input is
limited to 1 MB and 2,000 lines and must start with a supported timestamp;
unknown timestamps are rejected instead of using the imported pipeline's
placeholder date. BSD syslog timestamps omit the year, so `--bsd-year` is
required for those inputs. Model chunks are at most 100 lines and 8,000
characters. Log text is untrusted data, including text that resembles an
instruction. The model has no tool or command channel. Output can contain
redacted excerpts and proposed actions; review evidence against the original
source outside this CLI before any operational decision. No action is applied.

## Verification and status

Run the synthetic tests with:

```powershell
$env:PYTHONPATH='src'
python -m unittest tests.test_security_audit tests.test_security_audit_cli -v
```

Verification reporting in `runner.py` separates execution from verification:
an empty suite, timeout, blocked command or zero-test unittest/pytest run cannot
become `SUCCESS`, and RESULT omits raw command output. Separate candidate paths
for `command-runner`, `code-explore` and `spec-coder` are described in
[Worker roles](worker-roles.md). Detailed local command-log retention remains open.
None of this provides OS-level read-only isolation. Local GPU offload, live model
quality, prompt-injection resilience and production ingestion have not been
measured or accepted here.

Before any real-log or production use, review data classification and retention,
validate redaction against representative private samples in an approved
environment, establish the local service/authentication boundary, measure GPU
load and inference, and obtain independent review of findings and operational
effects. No live service or network configuration is changed by this candidate.
