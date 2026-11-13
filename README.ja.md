# Local AI Sidekick

[English](README.md) | [日本語](README.ja.md)

**強力なクラウドAIを主役に、手元のローカルGPUを補助役として活かす方法を探すプロジェクトです。** Claude・Gemini・ChatGPTなどと組み合わせながら、ローカルに任せる意味のある仕事を試行錯誤しています。

[![CI](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml)

## ひと目で分かる現状

| 項目 | 状況 |
| --- | --- |
| ローカルホスト（2026-11-17まで） | NVIDIA RTX 3070（8GB）。[2026-11-06の構成スナップショット](docs/architecture-2026-11-06.md)参照 |
| ローカルホスト（2026-11-18から） | RTX 5070 Ti（16GB）・メモリ64GBの新PC。[2026-11-18の構成](docs/architecture-2026-11-18.md)参照（計画段階。導入と実測は到着後） |
| 現在のローカルモデル | 確定したものはない。Qwenは利用終了。現行ホストでの後継は未確定 |
| このrepoにあるもの | Python CLI、範囲を決めたファイル方式の委譲（Lead AI → ローカルWorker）、Workerのロール、合成ログを使うオフライン監査の候補実装 |
| 根拠の扱い | コードと合成テストは「ソースに存在すること」の根拠であり、実機で動いたことの証明ではない |

## まず試す（GPU・モデル不要）

Python 3.10+があれば、このcheckoutで確認できます。

```powershell
$env:PYTHONPATH = 'src'
python -m sidekick.cli --help
python -m sidekick.security_audit --input tests/fixtures/security_audit/synthetic-auth.txt --source sshd --bsd-year 2026 --synthetic-or-public
```

モデル取得・パッケージインストールは不要です。監査例は合成fixtureのみを使い、修復操作は行いません。Bashでは各Pythonコマンドの先頭に `PYTHONPATH=src` を付けます。PowerShellの書き方と任意のモデル連携は[導入ガイド](docs/usage.md) / [詳細ガイド](docs/usage.ja.md)にあります。

## 仕組み

```text
ユーザー + Lead AI -> 範囲を決めたタスク -> ローカルWorker -> 結果と差分 -> Lead / 人のレビュー
```

要件・設計・安全判断・最終レビューはLeadが持ちます。Workerにはファイル・コマンドの制約がありますが、ホスト上のコマンド実行は完全なsandboxではありません。設定の既定値は `auto_git=false` / `auto_push=false`。WatcherモードはGit自動化を有効にするため、起動前に設定を確認してください。pushは明示opt-in、自動mergeは未対応です。[安全上の境界](SECURITY.md)も参照してください。

```mermaid
flowchart TD
    U["User / human approval"] --> L["Lead AI host: scope, design, review"]
    L --> D["Delegation assessment: LOCAL / LEAD / BLOCKED"]
    D -->|LOCAL only| H["sidekick.delegate: validate and publish TASK"]
    subgraph Local["Local development host / RTX 3070 context"]
        H --> T[".ai/TASK.md + rules"]
        T --> W["Watcher or manual runner"]
        W --> C["command-runner: approved commands, no LLM"]
        W --> M["code-explore / spec-coder / legacy coding path"]
        M --> O["Local Ollama: explicitly selected installed model"]
        O --> M
        C --> R["RESULT + state + observed verification"]
        M --> G["Scope / diff / secret guards; optional Git"]
        G --> R
    end
    R --> L
    D -->|LEAD or BLOCKED| L
    L -. "future experiments, not deployed" .-> P["Gemma adoption / Modal GPU / Kaggle"]
```

| 要素 | このrepoにあるもの |
| --- | --- |
| Leadの入口 | `AGENTS.md`、`CLAUDE.md`、委譲ルール、任意のホスト設定・bootstrap |
| 委譲 | `LOCAL / LEAD / BLOCKED` の判断と、`sidekick.delegate` による範囲を限定した `.ai/TASK.md` の発行 |
| CLIと実行 | `init` / `doctor` / `run` / `integrate` と `--watch` モード。手動実行、または別途起動するWatcher |
| モデル不要のロール | `command-runner`。承認済みコマンドを実行し、LLMとGit自動化は呼ばない |
| モデルを使うロール | 読取専用の `code-explore`、仕様限定の `spec-coder`、従来のcoding経路。設定したローカルOllamaを使う |
| レビュー材料 | `.ai/RESULT.md`、state、観測した検証結果、任意のGit制御。自動mergeはしない |
| Claude Code用資材 | 8つのagent定義、3つのskill、imports・hook。8サービスの稼働を意味しない |
| セキュリティログ監査候補 | 合成・公開入力のオフラインルール処理と、任意のローカルOllama補助。修復操作は行わない |

詳細は[ロール契約](docs/worker-roles.md)と[現在の実装・検証範囲](docs/current-status.md)を参照してください。`QUEUED`はタスクファイルの発行であり、Workerの実行完了ではありません。委譲helperはWatcherを起動しません。図は現行ホストで実装されている経路です。2026-11-18のハードウェア変更は[2026-11-18の構成](docs/architecture-2026-11-18.md)にまとめています。

## 現在のモデル状況

| 項目 | 確認できていること |
| --- | --- |
| Qwen | 現在は使っていない（本人の最新の訂正）。コード・env例の既定値 `qwen2.5:14b` と `Modelfile` の実験設定は残っており、現行コードではモデルを省略すると旧Qwen既定値が選ばれる |
| 後継モデル（現行ホスト） | repoと今回の文書確認からは確定できない。モデルを使う前に `SIDEKICK_MODEL` または `--model` で実際に導入したモデルを指定する |
| Gemma導入予定（2026-11-03記録） | Gemma 4 E4B、`gemma4:e4b` + `Q5_K_M`（5-bit）を希望。導入予定のままで、正式タグは未確認。GemmaがQwenの後継だと確認したものではない |
| 2026-11-18から | ローカルLLM基盤は新PC上のStrataへ。普段使いは Qwen3.8-Flash-Next IQ3_S、重い処理は DeepSeek V4.1-Flash、片方ずつ運用。実測までは計画として扱う（[2026-11-18の構成](docs/architecture-2026-11-18.md)） |

Gemmaの確認情報（2026-11-03）: [GoogleのGemma 4概要](https://ai.google.dev/gemma/docs/core)でE4Bを、[Ollamaの公式タグ一覧](https://ollama.com/library/gemma4/tags)で `gemma4:e4b` を確認。同一覧ではE4Bの `Q5_K_M` 正式タグを確認できていません。導入前に配布元・正確なファイルを選定し、VRAMへの適合と推論速度は実機で確認します。

## 読むところ

| 知りたいこと | 文書 |
| --- | --- |
| 現在の機能と確認できた範囲、連携の限界 | [現在の実装・検証範囲](docs/current-status.md) |
| RTX 3070 の用途比較と次に試すこと | [今後の展開案](docs/future-directions.md) |
| 必要な時だけ使うクラウドGPU、費用ガード、Kaggleの境界 | [Modal GPU実験場](docs/modal-gpu-experiments.md) |
| GPUを使わない確認、Workerの設定・運用 | [短い導入ガイド](docs/usage.md) / [詳細ガイド](docs/usage.ja.md) |
| 構成スナップショット（2026-11-06 / 2026-11-18）、文書一覧とフォルダ構成 | [docs入口](docs/README.md) |

## 押さえておく境界

- **委譲:** [AGENTS.md](AGENTS.md) と [.ai/DELEGATION.md](.ai/DELEGATION.md) が `LOCAL / LEAD / BLOCKED` を定義します（[運用ガイド](docs/usage.ja.md#自動委譲)）。タスクをキューに入れることは、完了を意味しません。
- **グローバル連携（任意）:** Codex / Claude Code の設定コードと指示ファイルはあります。ホスト設定を変える前に[連携ガイド](docs/usage.ja.md#グローバル連携任意)と[連携の確認範囲](docs/current-status.md#cloud-ai-integration-boundaries)を確認してください。Gemini / ChatGPT 製品との接続は検討段階で、このファイル方式自体が動作するconnectorを意味しません。
- **別システム:** HomeLab / OpenClaw はこのrepoの外です。Windows Defenderの状態収集はHomeLab側の運用で、このrepoの合成ログ監査候補とは分けて扱います。

## なぜローカルか

当初はクラウドAIのトークン節約を重視していました。いまの使い方では、クラウド側に任せてどんどん作れる場面が増えたので、ローカルに任せる理由を考え直しています。短い分類・抽出、ローカル検索の補助、音声文字起こしなどを、より単純な方法と比較予定で、coding offload は用途候補の一つです。クラウドが常に安い・速いという主張ではありません。

## ライセンス

[MIT](LICENSE)。
