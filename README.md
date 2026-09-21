# Local AI Sidekick

> Ollama を使ってローカルで動作する AI コーディング Worker。Lead/Worker の委譲範囲を明確にし、安全な Git 自動化と人間によるレビューを組み合わせます。

[![CI](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml)

## 目的

高価なフロンティア AI のトークン消費を大幅に抑えるため、役割分担を明確にします。

- **Lead AI**: アーキテクチャ設計、戦略的判断、タスク範囲の決定、最終コードレビューを担当します。
- **Local Sidekick**: ローカルリポジトリの調査、実装、テスト、自己修正、構造化された結果の生成を担当します。

Lead AI と Sidekick の通信は、ローカル Markdown ランタイムファイル（`.ai/TASK.md` と `.ai/RESULT.md`）を介して行います。これらのランタイムファイルはフレームワークリポジトリでは追跡せず、再利用可能な例は `templates/` 配下に置いています。

### 現在の対応範囲

| 機能 | 状態 |
| --- | --- |
| Phase 1 手動ローカル Worker | 実装済み |
| Phase 2 安全なブランチ / コミット自動化 | 実装済み |
| LOCAL / LEAD / BLOCKED の自動委譲 | 実装済み |
| Claude Code Lead 連携 | 実装済み |
| Codex / Claude のグローバル SessionStart ブートストラップ（`sidekick integrate`） | 実装済み |
| 自動 push | **オプトインのみ。既定値は OFF** |
| 自動 merge | 非対応 |

独立検証と人間による承認境界については [AI Engineering Factory 連携](docs/factory-integration.md) を参照してください。  
セキュリティモデル、脅威境界、脆弱性報告については [Security Policy](SECURITY.md) を参照してください。

---

## 自動委譲

```text
User -> Lead Host (Codex/Astra-compatible, Claude Code, ...) -> Delegation Policy -> LOCAL / LEAD / BLOCKED
                                            |
                                      LOCAL only
                                            v
TASK.md -> Existing Watcher -> Local Sidekick -> RESULT.md -> Lead Review
                                  implementation / test / self-fix
                                  ai/<task-id> -> READY_FOR_REVIEW
```

[AGENTS.md](AGENTS.md) は、通常のユーザー要求を処理する前に Lead が
[.ai/DELEGATION.md](.ai/DELEGATION.md) を適用するよう指示します。

Lead は要求内容を意味的に分類し、標準ライブラリのみで実装された helper がその判定を検証して、TASK.md をアトミックに発行します。これは命令ベースの委譲レイヤーであり、独立した自然言語分類器や新しい daemon を追加するものではありません。

`.ai/DELEGATION.md` は Lead Host に依存しない、このポリシーの唯一の正本です。[CLAUDE.md](CLAUDE.md) は Claude Code 向けにポリシーを複製せず、このファイルと AGENTS.md / RULES.md を import します。詳細は下の [対応 Lead Host](#対応-lead-host) を参照してください。

Astra / Antigravity など AGENTS.md を自動読込しない Host では、AGENTS.md とポリシーを workspace instruction に一度登録してください。Claude Code 以外の Host 固有の自動読込については、このリポジトリでは検証していません。

- **LOCAL**: 範囲が限定された調査、小〜中規模の実装、リファクタリング、テスト、修正、format、lint、README / docs / config、反復的な編集。
- **LEAD**: 設計、Security / IAM、クラウド・破壊的操作・deployment に関する判断、最終レビュー、Worker が BLOCKED になった場合の復旧。
- **BLOCKED**: 要件が曖昧、対象ファイル範囲が不明、受け入れ条件がない、信頼度が低い、または安全でないタスクデータを含む場合。TASK は作成しません。

[例](docs/delegation-request.example.json) に従って JSON を用意し、Worker の commit に混入しないよう対象リポジトリの外に保存します。具体的なファイルパス、単一行フィールド、および `src/sidekick/delegate.py` の `SAFE_COMMANDS` に含まれるコマンドを使用してください。任意の shell / interpreter コマンドは拒否されます。

```powershell
# After installing this repository with pip install -e .
sidekick-delegate --repo-root <target-repository> --request <assessment.json> --dry-run
sidekick-delegate --repo-root <target-repository> --request <assessment.json>
# In another terminal, after reviewing target repo/remote and push settings:
.\scripts\watch-sidekick.ps1 -RepoRoot <target-repository>
```

macOS / Linux では `sidekick-delegate ...` と `sidekick --repo-root <target-repository> --watch` を使用します。

対象リポジトリには、既存の Phase 2 / Ollama セットアップ、RULES.md、各種 decision が引き続き必要です。helper は Watcher を起動せず、push 設定も変更しません。

新しい自動委譲を無効化するには `$env:SIDEKICK_DELEGATION_ENABLED = "false"`
（POSIX: `export SIDEKICK_DELEGATION_ENABLED=false`）を設定します。すでに queue 済みのタスク消費を止めるには Ctrl+C で Watcher を停止してください。委譲を無効化しても queue 済みタスクはキャンセルされません。

**トラブルシューティング:** `QUEUED` は「送信済み」であり「完了」ではありません。何も実行されない場合は、Watcher の terminal、対象 path、Ollama / model の利用可否、Git preflight を確認してください。`ALREADY_QUEUED` / `ALREADY_HANDLED` は意図した重複排除です。

`RESULT.md` と `state.json` を確認し、直前の終了結果をレビューした後にだけ `--after-review` を使用してください。修正版を再実行する場合は新しい `task_id` が必要です。`BLOCKED` / `FAILED` および中断された実行は polling で自動再開されません。

古い lock を削除する前に owner を確認し、生存している Worker がある場合は停止してください。経過時間だけを理由に lock を奪ってはいけません。破損した state は履歴を削除するのではなく、信頼できる copy から修復してください。従来 CLI は custom path に対応していますが、自動委譲では現在、既定の `.ai/TASK.md` path が必須です。

## グローバル連携（任意）

Codex と Claude Code が、毎回「Sidekick を使って」「LOCAL/LEAD を確認して」と指示しなくても、**任意の Git リポジトリで自動的に委譲を認識する**ようにするには、次を **1 回だけ**実行します。

```bash
pip install -e ".[dev]"
sidekick integrate --global --host all
sidekick integrate --status
```

以降は次だけで開始できます。

```bash
cd ~/projects/foo
codex
# or
cd ~/projects/foo
claude
```

ユーザーが毎回入力する必要があるのはこれだけです。

**インストールされる内容。** `sidekick integrate` はグローバル設定に小さな SessionStart 連携を追加し、軽量な `ai-dev-bootstrap` entrypoint を呼び出します（`ai-dev-bootstrap` または `python -m sidekick.bootstrap` で直接実行することもできます）。

- **Claude Code**: `~/.claude/settings.json` に `SessionStart` hook を追加し、`ai-dev-bootstrap --json` を実行して、その出力を `additionalContext` として注入します。
- **Codex**: `~/.codex/AGENTS.md` に識別可能な instruction block を追記し、session 開始時に `ai-dev-bootstrap` を実行して、現在のリポジトリに `.ai/DELEGATION.md` が存在する場合はそれに従うよう指示します。Codex の hook schema は新しく変更も続いているため、推測で hook を利用せず、文書化された安定したグローバル `AGENTS.md` を使用します。

`ai-dev-bootstrap` が確認するのはローカル状態だけです。`cwd`、Git リポジトリかどうか、`.ai/DELEGATION.md` / `.ai/RULES.md` の有無、Worker lock の保持状態、AI Engineering Factory が存在するように見えるかを確認します。

テスト、Ollama inference、Factory 検証、`git fetch` / `pull`、その他の network call は実行しません。またリポジトリにも書き込みません。短く、上限付きで、secret を含まない Development Context block を出力するだけです。

```text
AI DEVELOPMENT ENVIRONMENT
Repository:
/home/you/projects/foo
Local AI Sidekick:
NOT_INITIALIZED
...
```

**この context を受け取った後の動作。** Lead Host は従来どおり `.ai/DELEGATION.md` を適用します（上の「自動委譲」を参照）。LOCAL の作業は `sidekick-delegate` 経由で Worker に渡し、LEAD の作業は Lead Host が保持し、BLOCKED の作業は人間の判断を待って停止します。

対象リポジトリにまだ `.ai/` がない場合、Lead は **最初の LOCAL 委譲の直前にだけ**、非破壊の `sidekick init .` を実行します。session 開始時に先回りして実行せず、`--force` も使用しません。

Watcher の起動は引き続き別の明示的な操作です（上の「トラブルシューティング」を参照）。`ai-dev-bootstrap` が Watcher を起動・停止・管理することはありません。

**AI Engineering Factory** は context 上で `AVAILABLE` / `CONFIGURED` / `UNAVAILABLE` として **検出されるだけ**で、自動実行されません。実際に実行するタイミングは [factory-integration.md](docs/factory-integration.md) を参照してください。

**安全性と冪等性。** インストールは既存設定へ merge する方式で、何度実行しても安全です。

- 既存の `~/.claude/settings.json` の hook と `~/.codex/AGENTS.md` の内容はそのまま保持し、Sidekick 自身の識別済み entry だけを追加または更新します。
- 同じ install command を 10 回連続で実行しても最終状態は同じです。hook や block が重複しません。
- 既存の `settings.json` が壊れている場合は、修復前に `settings.json.bak-<timestamp>` として backup し、黙って破棄しません。
- Sidekick、Factory、Ollama、Git が存在しない、または設定不備でも、`ai-dev-bootstrap` は context 上で `UNAVAILABLE` / `NOT_INITIALIZED` / `DEGRADED` と報告するだけです。Codex や Claude Code 自体の起動を妨げず、`.ai/RULES.md` や Fail-Closed の BLOCKED 経路を弱めません。

**その他のコマンド:**

```bash
sidekick integrate --global --host codex           # Codex only
sidekick integrate --global --host claude          # Claude Code only
sidekick integrate --global --host all --dry-run   # preview changes, write nothing
sidekick integrate --status                        # show current install state
sidekick integrate --remove --host all             # uninstall (only our own entries)
```

**無効化 / uninstall:** `sidekick integrate --remove --host all` は SessionStart hook と識別済み `AGENTS.md` block だけを削除し、その他のグローバル設定には触れません。グローバル設定を変更せず委譲だけ無効化したい場合は、前述の `SIDEKICK_DELEGATION_ENABLED=false` を使用します。

**トラブルシューティング:** session が context を取得していないように見える場合は、`sidekick integrate --status` で install 状態を確認し、対象リポジトリ内で `ai-dev-bootstrap` を直接実行して raw output を確認してください。

Windows では hook command を `sys.executable` から生成するため、追加の PATH 設定なしで PowerShell、`cmd.exe`、WSL2 から動作します。空白を含む path は自動的に quote されます。

## 対応 Lead Host

`AGENTS.md` と `.ai/DELEGATION.md` は Host 非依存です。現在、次の Lead Host に対応しており、どちらも LOCAL の作業を同じ `sidekick.delegate` helper、Watcher、Ollama Worker へ委譲します。

- **Codex / Astra-compatible host**: `AGENTS.md` を直接読み込みます。自動読込しない場合は workspace / system instruction に一度登録してください。
- **[Claude Code](https://claude.com/claude-code)**: リポジトリ root の [CLAUDE.md](CLAUDE.md) にある `@import` を通じて、`AGENTS.md`、`.ai/DELEGATION.md`、`.ai/RULES.md` を自動読込します。

Worker の実装経路は、どちらの Host にも依存しません。

### Claude Code のセットアップ

1. Claude Code でこのリポジトリを project root として開きます（この directory で `claude` を実行するか、Claude desktop app で folder を開きます）。
2. Claude Code が `CLAUDE.md` を自動で読み込み、そこから `AGENTS.md`、`.ai/DELEGATION.md`、`.ai/RULES.md` を import します。追加設定は不要です。
3. Claude Code 内で `/memory` を実行し、import が読み込まれていることを確認します。active project instruction に使われているすべての file が一覧表示され、上記 3 file も確認できます。
4. Claude Code に通常の task を与えます。他の Lead Host と同じ LOCAL / LEAD / BLOCKED policy を適用し、LOCAL の作業では [自動委譲](#自動委譲) の記載どおり `sidekick.delegate` を実行します。

## 既存 Worker アーキテクチャ

![Local AI Sidekick Technical Architecture](docs/images/architecture.jpg)

```text
Lead Host (Codex/Astra-compatible, Claude Code, ...)
  │
  │ writes .ai/TASK.md
  ▼
Local Repository
  │
  ├── .ai/
  │   ├── RULES.md       (Permanent rules)
  │   ├── TASK.md        (Task specification)
  │   ├── RESULT.md      (Execution output)
  │   └── DECISIONS.md   (Architecture decisions)
  │
  ├── prompts/
  │   └── sidekick-system.md
  │
  ├── scripts/
  │   ├── run-sidekick.ps1 (Windows runner)
  │   └── run-sidekick     (Bash runner)
  │
  ├── config/
  │   └── sidekick.example.env
  │
  ├── docs/
  │   ├── architecture.md
  │   └── factory-integration.md
  │
  ├── templates/
  │   ├── TASK.example.md
  │   └── RESULT.example.md
  │
  └── README.md
        │
        ▼
Local Sidekick (Ollama Runner)
        │
        ├── repository exploration (Allowed Files only)
        ├── implementation
        ├── lint / format / validation
        ├── unit test execution
        ├── self-fix loop
        └── RESULT.md & git diff generation
```

詳細な技術仕様は [docs/architecture.md](docs/architecture.md) を参照してください。

---

## 動作要件

- **OS**: Windows 10/11、macOS、Linux
- **Python**: 3.10+（標準ライブラリのみ。外部 pip dependency は不要）
- **PowerShell**: 7+（または Windows PowerShell）/ Bash
- **Git**: 2.30+
- **Ollama**: install 済みで `http://localhost:11434` で起動していること

---

## Ollama とモデルのセットアップ

Ollama が起動していることを確認します。

```powershell
ollama list
```

標準モデル（`qwen2.5:14b`）を install します。

```powershell
ollama pull qwen2.5:14b
```

### GPU Offload Layer 上限（動画再生・デスクトップ操作との共存）

Ollama が VRAM を 100% 占有するのを防ぎ、動画再生、window manager、その他の GPU workload と共存できるように `Modelfile` を用意しています。

```dockerfile
FROM qwen2.5:14b
PARAMETER num_gpu 25
```

layer 上限を適用します。

```powershell
ollama create qwen2.5:14b -f Modelfile
```

install 済みの任意モデルは、環境変数 `SIDEKICK_MODEL` または CLI flag `--model` で指定できます。

---

## インストールとクイックスタート

1. package を install します。

   ```bash
   git clone https://github.com/moruku36/local-ai-sidekick.git
   cd local-ai-sidekick
   python -m pip install -e ".[dev]"
   ```

2. **対象リポジトリを初期化**します（`.ai/` governance、rules、decisions、`.gitignore` を作成）。

   ```bash
   sidekick init /path/to/repo
   ```

3. **環境の readiness を診断**します（Git repo、Ollama 接続、model 利用可否、guardrail を確認）。

   ```bash
   sidekick doctor /path/to/repo
   ```

4. （任意）example から local configuration を作成します。

   ```powershell
   Copy-Item config\sidekick.example.env .env
   ```

5. 手動 TASK.md workflow を使う場合は runtime template を copy します。自動委譲では `.ai/TASK.md` がアトミックに作成されるため、委譲 task では不要です。

   ```powershell
   Copy-Item templates\TASK.example.md .ai\TASK.md
   Copy-Item templates\RESULT.example.md .ai\RESULT.md
   ```

   `.ai/TASK.md` と `.ai/RESULT.md` は runtime file です。framework の `.gitignore` により通常の Git status / commit から除外され、Sidekick も既定では commit しません。明示的に opt-in した場合だけ、secret scan 後にこれら既知の runtime path を force-add します。

設定パラメータ:

- `SIDEKICK_OLLAMA_BASE_URL`: Ollama endpoint（既定: `http://localhost:11434`）
- `SIDEKICK_MODEL`: 既定モデル（既定: `qwen2.5:14b`）
- `SIDEKICK_MAX_RETRIES`: test failure 時の自己修正回数（既定: `2`）
- `SIDEKICK_TIMEOUT_SECONDS`: request timeout 秒数（既定: `180`）
- `SIDEKICK_AUTO_PUSH`: task branch を自動 push（**既定: `false`**）
- `SIDEKICK_COMMIT_TASK_FILE`: runtime TASK.md を commit（**既定: `false`**）
- `SIDEKICK_COMMIT_RESULT_FILE`: runtime RESULT.md を commit（**既定: `false`**）

---

## TASK.md ワークフロー

### 1. Lead AI が `.ai/TASK.md` を作成

Lead AI は、範囲を限定した要件を `.ai/TASK.md` に記述します。

```markdown
# Current Task

## Goal
Implement a string utility function to reverse text.

## Background
Need a string reverser in src/text_utils.py.

## Allowed Files
- src/text_utils.py
- tests/test_text_utils.py

## Forbidden Operations
- Do not modify any files outside Allowed Files

## Requirements
- Provide `reverse_string(text: str) -> str`

## Acceptance Criteria
- `python -m unittest discover tests` succeeds

## Allowed Commands
- python -m unittest discover tests

## Review Points
- Function docstring and type annotations
```

---

## Sidekick の実行

`pip install -e .` 後の primary CLI は次です。

```powershell
sidekick --repo-root .
```

既存の PowerShell wrapper も互換性のため利用できます。

```powershell
.\scripts\run-sidekick.ps1
```

オプション:

- `-RepoRoot <path>`: 対象リポジトリ directory（既定: `.`）
- `-Model <model_name>`: model override（例: `-Model "qwen2.5:14b"`、軽量な代替として `-Model "qwen2.5-coder:7b"`）
- `-EnvFile <path>`: custom `.env` file の path

Linux / macOS:

```bash
sidekick --repo-root . --model qwen2.5:14b
```

`./scripts/run-sidekick` wrapper も引き続き利用できます。

---

## RESULT.md のレビュー

処理完了後、Sidekick は `.ai/RESULT.md` を生成します。

- **Status**: `SUCCESS`、`PARTIAL`、`BLOCKED`、`FAILED` のいずれか
- **Summary**: 実施した変更の簡潔な概要
- **Files Changed**: 変更 / 作成した file の一覧
- **Commands Executed**: 実行した command と exit code
- **Test Results**: test 実行結果
- **Errors**: test failure 時の診断 error
- **Decisions Required**: Lead AI の判断が必要な項目
- **Git Diff Summary**: `git diff --stat` または untracked file の概要

Lead AI は `.ai/RESULT.md` を確認し、diff を検証して、受け入れるか追加修正を行います。

---

## Git ワークフローと安全性（Phase 1 / Phase 2）

### Phase 1 手動ワークフロー

- **自動 merge / push なし**: Sidekick は local file を変更し、許可された check を実行します。`scripts/run-sidekick.ps1` で実行します。

### Phase 2 自律 Git 自動化

`scripts/run-sidekick-phase2.ps1` または `scripts/watch-sidekick.ps1` から実行した場合:

1. **Preflight Check**: Git working tree が clean か、remote 設定が妥当かを確認します。
2. **Automated Branching**: base branch から `ai/<task-id>` へ自動 switch、または branch を作成します。`main` での直接実行や push は厳格に禁止します。
3. **Diff Guard**: commit 前に、すべての変更 file を `Allowed Files`（および `.ai/TASK.md` / `.ai/RESULT.md`）と照合します。未許可の変更があれば commit / push を即座に block します（`status: BLOCKED`）。
4. **Secret Scan**: 変更 file に API key、AWS token、private key、高 entropy secret が含まれないか検査します。secret を検出した場合は停止します（`status: BLOCKED_SECRET_DETECTED`）。
5. **Safe Commit & Push**: source の変更を `ai(<task-id>): <summary>` という message で commit します。push は **既定で無効**で、明示的に有効化した場合も `origin ai/<task-id>` に限定されます。
6. **Final Status**: `.ai/state.json` と `.ai/RESULT.md` を `READY_FOR_REVIEW` にし、Lead AI または人間による review 待ちにします。

---

## Phase 2 Watcher モード（自律バックグラウンド Worker）

Task Watcher を起動し、`.ai/TASK.md` を継続監視します。

```powershell
.\scripts\watch-sidekick.ps1 -Interval 5
```

- `.ai/TASK.md` の SHA256 hash を計算し、同じ task の重複実行を防ぎます。
- 委譲機構と共有する exclusive `.ai/sidekick.lock` で concurrency を制御します。stale lock は Lead による確認が必要で、経過時間だけを理由に動作中 Worker の lock を奪いません。
- 実行 state を `.ai/state.json` に記録します。

---

## 実 Ollama E2E テスト（専用検証レーン）

Phase 2 end-to-end test は **実際の local Ollama instance** を呼び出すため、意図的に opt-in にしています。通常の pull request CI では高速かつ deterministic な test suite を実行し、外部 runtime を必要とする test は skip します。

専用 helper を使って local で実 E2E suite を実行する場合:

```bash
python scripts/run-real-e2e.py --model qwen2.5:14b
```

環境変数から実行する場合:

```powershell
$env:SIDEKICK_RUN_REAL_OLLAMA_E2E = "true"
python -m unittest tests.test_phase2_e2e -v
```

Linux / macOS:

```bash
SIDEKICK_RUN_REAL_OLLAMA_E2E=true python -m unittest tests.test_phase2_e2e -v
```

GitHub Actions では、実 Ollama 実行を別の manual workflow に分離しています。

- [Real Ollama E2E (Manual Lane)](.github/workflows/e2e-ollama.yml) — `workflow_dispatch` から任意の model を選択して実行できます。

---

## セキュリティモデルと運用上の注意

> [!WARNING]
> **ローカル実行と信頼できないタスクに関する警告**:
> この tool は subprocess を通じて、ユーザーの machine 上で code、build、test command を実行します。危険な command（`rm -rf`、破壊的な cloud write、`git reset --hard`）や宣言されていない file edit を guard しますが、command 実行自体は host environment と直接やり取りします。**未知の source から受け取った、信頼できない・未レビューの task は実行しないでください。**
>
> 完全な threat boundary、保護対象 / 対象外、脆弱性報告手順は [SECURITY.md](SECURITY.md) を参照してください。

- **Permanent Rules**: `.ai/RULES.md` に保存します。
- **Allowed Files List & Diff Guard**: path traversal と未宣言 file への access を、実行時と Git commit 前の両方で block します。
- **Immutable Files**: `.ai/DECISIONS.md`、`.git/`、`.env*` は変更できません。
- **Destructive Command Blocking**: `rm -rf`、`git reset --hard`、`terraform apply`、`aws/az/gcloud` の write operation に一致する command を intercept して拒否します。
- **Secret Redaction & Pre-commit Scanning**: output 内の credential を検出して mask し、raw secret を含む commit を block します。
- **Git Protection**: Local LLM は raw git command を実行しません。すべての Git operation は hardening された Python manager が実行し、`main` への push は block します。
- **Runtime Task Data**: `.ai/TASK.md` / `.ai/RESULT.md` は ignore される runtime file です。version 管理する example は `templates/` 配下に置きます。Sidekick は既定ではこれらを commit しません。
- **Task Data Isolation Recommendation**: このリポジトリが提供するのは Sidekick framework です。実際の proprietary project では、機密性のある task / result data をこの framework repository に commit せず、対象 project repository 側で Sidekick を構成してください。
- **Independent Verification**: より強い evidence、phase contract、merge approval boundary が必要な場合は [AI Engineering Factory 連携](docs/factory-integration.md) を利用してください。

---

## ライセンス

この project は [MIT License](LICENSE) で提供します。

---

## 参考・謝辞

この project の architecture と Lead / Worker の役割分担の考え方は、Cognition の Local Fusion から着想を得ています。

- [Cognition: Local Fusion](https://cognition.com/blog/local-fusion)

関連 project:

- [AI Engineering Factory integration](docs/factory-integration.md) — 独立検証、phase contract、人間が承認する merge boundary
