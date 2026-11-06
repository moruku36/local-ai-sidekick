# Local AI Sidekick

[English](README.md) | [日本語](README.ja.md)

**強力なクラウドAIを主役に、手元の NVIDIA RTX 3070 を補助役として活かす方法を探すプロジェクトです。** Claude・Gemini・ChatGPT などと組み合わせながら、ローカルGPUに任せる意味のある仕事を試行錯誤しています。

- **現在のモデル:** Qwen はもう使っていません。コードの既定値や過去の実験設定にはQwenが残っていますが、現在の稼働構成を表すものではありません。後継モデルの正確なタグ・導入状況・実機稼働は、この更新では確認していません。
- **このrepoにあるもの:** Ollama を使う coding Worker、範囲を決めた委譲、TASK / RESULT、Git制御、役割別の実行経路、合成ログを使うオフライン監査の候補実装。コード・合成テストの存在と実機運用の実績は区別します。
- **未実装・今後:** 短い分類・抽出、ローカル検索の補助、音声文字起こしなどを比較予定。各クラウド製品との接続も、実装や検証の有無を確認しながら探ります。coding offload は用途候補の一つです。

当初はクラウドAIのトークン節約を重視していました。いまの自分の使い方では、クラウド側に任せてどんどん作れる場面が増えたので、ローカルに任せる理由を考え直しています。クラウドが常に安い・速いという主張ではありません。

[![CI](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml)

## 現在の構成とアーキテクチャ — 2026-11-06

現在のrepoの中心は、Python CLIと、Lead AIホストから範囲を決めてWorkerへ渡すローカルファイル方式です。下図は実装されている経路を示し、実機の稼働確認ではありません。Qwenは現在使っておらず、Gemma導入とModal / Kaggle実験は未検証の計画として扱います。HomeLab / OpenClaw は別システムです。

[11月6日の構成一覧・アーキテクチャ図・ネットワーク図・根拠](docs/architecture-2026-11-06.md)を参照してください。

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

詳細は[ロール契約](docs/worker-roles.md)と[連携の確認範囲](docs/current-status.md#cloud-ai-integration-boundaries)を参照してください。`QUEUED`はタスクファイルの発行であり、Workerの実行完了ではありません。委譲helperはWatcherを起動しません。

## 現在のモデル状況

| 項目 | 確認できていること |
| --- | --- |
| ローカルGPU | NVIDIA RTX 3070 |
| Qwenの利用 | 現在は使っていない。本人の最新の訂正を反映 |
| 残っているQwen設定 | コード・env例の既定値は `qwen2.5:14b`。`Modelfile` は過去のQwen実験設定 |
| 現在の後継モデル | repoと今回の文書確認からは確定できない |
| 実行時の指定 | モデルを使う前に `SIDEKICK_MODEL` または `--model` で実際に導入したモデルを指定する |

今回の変更は文書のみです。コードの既定値変更、モデル導入、GPUでの動作確認は行っていません。現行コードではモデルを省略すると旧Qwen既定値が選ばれる点に注意してください。

### 2026-11-03に記録したGemma導入予定

| 項目 | 予定・確認状況 |
| --- | --- |
| ローカルGPU | NVIDIA RTX 3070 |
| 採用予定モデル | Gemma 4 E4B |
| 希望する量子化 | `gemma4:e4b` + `Q5_K_M`（5-bit）。希望する構成の表記であり、実行可能な正式タグは未確認 |
| 導入状況 | 導入予定。今回の文書更新ではインストール・ダウンロード・ベンチマークは行わない |
| 今後の確認 | E4B Q5_K_Mの配布ファイル・正式なOllamaタグ、VRAMへの適合、推論速度、他の候補と比べた品質 |

以前記録した導入予定です。Gemmaが現在導入済み・稼働中だと確認したものではなく、Qwenを使っていないことから後継モデルを推定しません。RTX 3070での実際の性能も未確認です。

**2026-11-03確認の公式情報:** [GoogleのGemma 4概要](https://ai.google.dev/gemma/docs/core)でE4Bを、[Ollamaの公式タグ一覧](https://ollama.com/library/gemma4/tags)で`gemma4:e4b`を確認しました。同一覧ではE4Bの`Q5_K_M`正式タグを確認できていません。導入前に配布元・正確なファイルを選定します。モデル全体がVRAMに収まるか、実際の推論速度・品質は実機での確認が必要です。

## 読むところ

Python 3.10+があれば、GPUを使わずにこのcheckoutで試せます。

```powershell
$env:PYTHONPATH = 'src'
python -m sidekick.cli --help
python -m sidekick.security_audit --input tests/fixtures/security_audit/synthetic-auth.txt --source sshd --bsd-year 2026 --synthetic-or-public
```

モデル取得・パッケージインストールは不要です。監査例は合成fixtureのみを使い、修復操作は行いません。Bashでは各Pythonコマンドの先頭に `PYTHONPATH=src` を付けます。

| 知りたいこと | 文書 |
| --- | --- |
| 現在の機能と確認できた範囲、連携の限界 | [現在の実装・検証範囲](docs/current-status.md) |
| RTX 3070 の用途比較と次に試すこと | [今後の展開案](docs/future-directions.md) |
| 必要な時だけ使うクラウドGPU、費用ガード、Kaggleの境界 | [Modal GPU実験場](docs/modal-gpu-experiments.md) |
| GPUを使わない確認、Workerの設定・運用 | [短い導入ガイド](docs/usage.md) / [詳細ガイド](docs/usage.ja.md) |
| 文書一覧とフォルダ構成 | [docs入口](docs/README.md) |

## 既存Workerの位置づけ

```text
ユーザー + Lead AI -> 範囲を決めたタスク -> ローカルWorker -> 結果と差分 -> Lead / 人のレビュー
```

要件・設計・安全判断・最終レビューはLeadが持ちます。Workerは許可ファイルとコマンドに制約がありますが、ホスト上のコマンド実行は完全なsandboxではありません。設定の既定値は `auto_git=false` / `auto_push=false` ですが、WatcherモードはGit自動化を有効にするため、起動前に設定を確認してください。pushは明示opt-in、自動mergeは未対応です。[安全上の境界](SECURITY.md)も参照してください。

Windows Defenderの単純な状態収集にGPUは不要です。HomeLab側の運用と、このrepoの合成ログ監査候補は分けて扱います。

## ライセンス

[MIT](LICENSE)。
