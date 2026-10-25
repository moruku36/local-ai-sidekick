# Current status / 現在の実装・検証範囲

[Documentation index](README.md) | [今後の展開案](future-directions.md)

確認日: **2026-10-25**。コード読解の基準は main `ae7f8d8`。
「実装あり」はコードが存在する意味です。合成テストの成功は、実モデルの品質・GPU性能・常用運転の確認を意味しません。

## 現在あるもの

| 項目 | コード・確認できること | 証拠の限界 |
| --- | --- | --- |
| CLI / 初期化 / 診断 | [cli.py](../src/sidekick/cli.py)、[onboarding.py](../src/sidekick/onboarding.py): init / doctor / run / watch / integrate | doctorのreadinessと、実推論・実運用の成功は別 |
| 委譲 | [delegate.py](../src/sidekick/delegate.py): Leadのassessmentを検査し、LOCALのみTASKを発行 | 意味的な安全分類はLeadの責任。QUEUEDは完了ではない |
| 既存coding Worker | [runner.py](../src/sidekick/runner.py)、[ollama_client.py](../src/sidekick/ollama_client.py): 許可ファイル読取、Ollama提案、編集、検証、自己修正、RESULT | 実Ollama E2Eは別のopt-inレーン。今回未実行 |
| Git制御 | [git_manager.py](../src/sidekick/git_manager.py)、[config.py](../src/sidekick/config.py): task branch、diff guard、secret scan、任意commit/push | auto_git / auto_pushは既定false。自動mergeは未対応。完全なOS sandboxではない |
| command-runner | [runner.py](../src/sidekick/runner.py): 承認済みコマンドのみ、モデル・Git自動化を呼ばず観測を返す | GPU不要。詳細ログ保存は未実装、`log_ref: null` |
| code-explore / spec-coder | [role_contract.py](../src/sidekick/role_contract.py)、[code_explore.py](../src/sidekick/code_explore.py): 読取調査と仕様限定編集の候補経路 | 合成・mock試験と実機品質は別。具体的な制約は[role guide](worker-roles.md) |
| ローカル監査候補 | [security_audit.py](../src/sidekick/security_audit.py)、[pipeline](../src/sidekick/security_log_pipeline.py): 合成ログのルール処理、証拠照合、明示opt-inのlocal Ollama補助 | 実ログ・本番取り込み・live Ollama推論は未検証。修復操作は実行しない |
| Qwenの稼働 | 本人の利用申告 | モデルtag・量子化・VRAM・CPU分割・各Worker経路の実機結果は今回測定していない |

[Worker roles](worker-roles.md)と[監査候補](security-audit.md)を現行の操作説明とし、
[旧roadmap](worker-role-roadmap.md)の過去commitに対する観察を現在の欠陥の証拠にしないでください。

## Cloud AI integration boundaries

| 対象 | リポジトリにある接点 | 実証と案の境界 |
| --- | --- | --- |
| Codex | [AGENTS.md](../AGENTS.md)、[integrate.py](../src/sidekick/integrate.py)のグローバル指示block、bootstrap | 設定生成と合成テストの対象。特定アプリ・モデルでの常用や自動読込を一律には保証しない |
| Claude Code | [CLAUDE.md](../CLAUDE.md)のimports、[SessionStart hook](../.claude/hooks/session-start.sh)、設定生成 | repoの指示・hook資材が存在。実サービスでのend-to-end連携は今回未検証 |
| Gemini / ChatGPT | LeadがTASK/RESULTを介して使う組合せの探索対象 | 専用connectorや製品固有hookの実装・運用実証は、この確認範囲では確認していない |
| AI Governance Control | [明示的な引き渡し設計](factory-integration.md)、bootstrapの存在検出 | 自動実行・native adapter・独立検証済みという意味ではない |

本体のOllama clientにあるOpenAI互換HTTP endpointは**ローカルOllamaの呼出先**です。
ChatGPT製品との接続や、クラウドAPIへの送信を証明するものではありません。

## HomeLabとの境界

Home AI Engineering Lab由来の公開パイプラインを適応したものが、このrepoの監査候補です。
NUC、n8n、Compose、ネットワーク橋渡し、本番schedulerの稼働をSidekick側の実績として数えません。
Windows Defenderの単純な状態収集はGPU不要のHomeLab運用として分離します。

## この文書整理で確認したこと

2026-10-25、Windows / Python 3.11.9で通常suiteを実行し、152件中150件成功、実Ollama E2Eの2件はopt-inを無効にしてskipしました。最初のsandbox内実行では一時Git操作・ファイル置換の制限で失敗し、承認付き再実行で合格を確認しました。

CLI help、source compile、合成監査のoffline例も確認しました。監査例は `llm_status: NOT_REQUESTED`、`actions_executed: false`、検出2件です。相対リンク・節アンカー（配布テンプレートは配置先基準）、差分の空白、変更文書の既知secretパターンを検査しました。これは完全な秘密検知の保証ではありません。

コードの変更はありません。GPU実行・モデル取得・実Ollama E2E・実ログ投入は行っていません。上記の合格を実機運用済みという表記には置き換えません。
