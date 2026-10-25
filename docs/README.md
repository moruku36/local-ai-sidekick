# Documentation / 文書の入口

[English overview](../README.md) | [日本語の概要](../README.ja.md)

## 読む順番

1. [現在の実装・検証範囲](current-status.md): コード・合成テスト・本人申告・未検証を区別する。
2. [今後の展開案](future-directions.md): RTX 3070 の用途比較、一次資料、採用基準と実験案。
3. [Usage](usage.md) / [Workerの設定・運用ガイド](usage.ja.md): GPU不要の確認から、任意の委譲・Watcher・ホスト設定まで。

## 目的別の資料

| 文書 | 位置づけ |
| --- | --- |
| [Worker roles](worker-roles.md) | 現行の候補実装: command-runner / code-explore / spec-coder の能力と限界 |
| [Security audit](security-audit.md) | 合成・公開ログだけのオフライン候補。HomeLab本番移行や実GPU推論を示さない |
| [Architecture](architecture.md) | 既存coding Workerの技術設計。プロジェクト全体の主戦略ではない |
| [AI Governance Control integration](factory-integration.md) | 独立検証への明示的な引き渡し設計。ネイティブadapterの実証ではない |
| [Delegation request example](delegation-request.example.json) | 委譲helperへ渡す再利用用の例 |
| [TASK](../templates/TASK.example.md) / [RESULT](../templates/RESULT.example.md) | 再利用用テンプレート。実タスクや実行結果は別管理 |
| [Security policy](../SECURITY.md) | ホスト実行の境界・秘密情報・脆弱性報告 |

## 過去の設計・調査

| 文書 | 読み方 |
| --- | --- |
| [Worker role roadmap](worker-role-roadmap.md) | 2026-10-15の計画と旧commitの観察。候補実装後も残る評価項目を含む |
| [Runtime reliability research](runtime-reliability.md) | 旧READMEの2026-10-13調査案を保存。未実装・未再現の提案 |
| [Architecture decisions](../.ai/DECISIONS.md) | 過去の決定記録。トークン節約という当初の動機は履歴として残す |

## フォルダ構成

コードは移動せず、説明の入口を整理しています。

```text
README.md / README.ja.md  目的・現在・今後を短く伝える入口
docs/                    文書一覧、現状、運用、用途調査、過去設計
  images/                既存Worker設計の図
src/sidekick/            CLI、委譲、Worker、Git制御、監査候補の実装
  templates/            initで配布する指示・ルール等（実装側の資材）
  schemas/              監査イベント等の形式
tests/                   単体・合成試験、明示的opt-inの実Ollama E2E
  fixtures/             公開用の合成入力・fixture
scripts/                 OS別runner、Watcher、実E2E用helper
config/                  設定例（実際の.envは追跡しない）
prompts/                 Workerのsystem prompt
templates/               利用者向けTASK / RESULTの例
.ai/                     Leadの委譲方針・ルール・決定記録
.claude/                 既存Claude Code向けhook設定
.github/                 CIと手動実E2E workflow
AGENTS.md / CLAUDE.md     Leadの指示入口
Modelfile                既存Qwen実験設定（メモリ上限の保証ではない）
```

`.ai/TASK.md`、`.ai/RESULT.md`、state・lock等は対象checkoutの実行時データです。
利用者の秘密・実ログ・私的会話をテンプレートや公開文書へ混ぜないでください。
