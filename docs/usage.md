# Usage: a first look and optional Worker setup

[Documentation index](README.md) | [Detailed Japanese guide](usage.ja.md)

## Offline first look

From a checkout with Python 3.10+, these commands need no model, GPU or package installation:

```powershell
$env:PYTHONPATH = 'src'
python -m sidekick.cli --help
python -m sidekick.security_audit --input tests/fixtures/security_audit/synthetic-auth.txt --source sshd --bsd-year 2026 --synthetic-or-public
```

On Bash, prefix each Python command with `PYTHONPATH=src` instead. The audit example
prints rule-based findings from a synthetic fixture. It invokes no model and applies
no remediation. See the [audit guide](security-audit.md) for input restrictions.

## Optional model-backed Worker

The repository targets Windows, macOS and Linux. The Worker uses Python's standard
library; Git automation requires Git 2.30+. Model paths require an already running
local Ollama service and a suitable installed model. The configured default is
`qwen2.5:14b`; it is not a promise of full GPU residency on an 8 GB card.

If you decide to install the package and initialize a **target** repository:

```bash
python -m pip install -e .
sidekick init /path/to/target-repo
sidekick doctor /path/to/target-repo --model <installed-model-name>
```

`init` writes governance/entrypoint files in the target; `doctor` checks readiness,
including Ollama/model availability. Neither is evidence of successful inference.
Do not use `--force` to overwrite existing instructions as a routine setup step.
Review [configuration defaults](../config/sidekick.example.env) and the target's
rules before running a task. No model download is required just to inspect this project.

Use the [task template](../templates/TASK.example.md) for manual work, or follow
the [delegation guide](usage.ja.md#自動委譲) for a bounded helper submission.
The helper does not start the Watcher. Review Git settings before starting it:
Watcher mode enables Git automation, while automatic push remains opt-in.
The [role guide](worker-roles.md) explains the model-free command-runner and the
model-backed code-explore/spec-coder paths.

## Verification lanes

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
```

The normal suite uses synthetic fixtures and mocks; it does not establish live
GPU performance. Keep `SIDEKICK_RUN_REAL_OLLAMA_E2E` unset/false for offline testing.
The [real Ollama lane](usage.ja.md#実-ollama-e2e-テスト専用検証レーン) requires
separate explicit opt-in and is not part of the GPU-free first look.

Global host setup changes user settings and is optional. See the
[Japanese operating guide](usage.ja.md#グローバル連携任意),
[current evidence limits](current-status.md) and [security policy](../SECURITY.md).
