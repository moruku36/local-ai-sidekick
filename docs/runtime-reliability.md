# Runtime reliability research / 実行時の信頼性に関する調査案

[Documentation index](README.md) | [Current direction](future-directions.md)

Historical proposal from 2026-10-13, moved from both READMEs on 2026-10-25.
These references and proposed acceptance criteria are retained as research history;
they were not revalidated or reproduced during this documentation update.
This is a possible improvement to the coding Worker, not the main RTX 3070 strategy.
For implemented role paths, use [current status](current-status.md) and [Worker roles](worker-roles.md).

## Future Research — runtime reliability and profiling (2026-10-13)

**Status: proposed; not implemented or reproduced.** Priorities below are an investigation order, not release dates.

### Sources and reading scope

- [OpenClaw and Ollama in Agentic AI: Toward Fully Autonomous and Scalable AI Agent Systems](https://arxiv.org/abs/2607.28629v1) — K. I. Roumeliotis and R. Sapkota. Sections 2–4 of the accessible [paper full text](https://www.researchgate.net/publication/411138539_OpenClaw_and_Ollama_in_Agentic_AI_Toward_Fully_Autonomous_and_Scalable_AI_Agent_Systems) separate inference, runtime, execution, memory and governance. The prototype compares inference alone, stateless tools and persistent memory. Its host-mode deployment does not validate container isolation.
- [Author code and evaluation artifacts](https://github.com/Applied-AI-Research-Lab/OpenClaw-and-Ollama-in-Agentic-AI): the current repository includes enriched-input controls and leak correction beyond the accessible manuscript's smaller experiment. Treat these as distinct artifacts; pin their commit before reproduction.
- [Accelerating Post-Quantum Cryptography via LLM-Driven Hardware-Software Co-Design](https://arxiv.org/html/2602.09410v1) — Y. Liao, T. Adegbija and R. Lysecky. Use its profiling workflow as design input; it did not evaluate Ollama workers.

The following are **our adaptations**, not reproduced paper results. No per-turn JSON “Memory Anchor” method was located in the reviewed manuscript; that design below is our proposal. Runtime integration does not establish model-size independence, production safety or an expected coding-success uplift.

### Proposed improvements and acceptance criteria

| Priority | Improvement | Evidence required before adoption |
|---|---|---|
| P1 | Clarify the existing runtime boundaries instead of replacing the worker: Ollama proposes typed actions; a trusted controller owns state, authorization, deadlines and command execution. Invalid model output cannot invoke tools. | A model-generated command, path or permission change is rejected outside the approved task scope; every executed action maps to a registered operation and actual result. |
| P1 | Add a versioned task checkpoint (“state anchor”) containing task/requirement version, goal, candidate digest, TDD stage where applicable, last independently observed test result, next permitted operation IDs and remaining budget. Store it outside model authority. | Restart with stale/corrupt checkpoints, changed candidates or another task cannot reuse evidence or widen permissions. Resume reconciles uncertain effects before retry; restart does not reset budgets. No fabricated RED evidence for documentation-only work. |
| P2 | Evaluate memory with provenance: task-local working state first; any cross-task memory is separately scoped, attributable, expirable and treated as untrusted input. | Tests cover goal continuity, stale requirements, poisoned notes and cross-task contamination. Retrieved text cannot alter policy, approval or accepted tests. |
| P2 | Compare identical model/input/budget runs: current worker; runtime without persistence; runtime with persistence; optionally structured checkpoints. Keep isolation and acceptance oracle identical. | Report independent task success, actual tool effects, recovery, scope violations, latency, retries and token/resource cost, including all failures. Tool claims and worker RESULT alone are insufficient. |
| P3 | Pilot local source/profile-log summarization for performance investigations, with function references and evidence links; compare source-only hypotheses with measured hotspots. | Hold out profiling results when evaluating source-only predictions; record compiler/build/workload conditions and ranking agreement. Unmeasured latency remains unknown; no automatic FPGA or cloud recommendation. |

### Integration boundary

Build on [the existing Factory handoff](factory-integration.md): Lead scopes work, Sidekick proposes a candidate, AI Governance Control independently verifies it, and a human reviews the PR. A native adapter or OpenClaw dependency is a separate future decision. OpenClaw is an architectural reference here, not an installed runtime or a new protocol guarantee.

**Next research milestone:** define the checkpoint contract and a small fixed offline coding/recovery task set, then record a reproducible baseline before choosing a runtime change.


---

## Future Research — 実行時の信頼性と性能調査（2026-10-13）

**状態：改善提案。未実装・未再現です。** 優先度は調査順で、リリース期限ではありません。

### 出典と確認範囲

- [OpenClaw and Ollama in Agentic AI: Toward Fully Autonomous and Scalable AI Agent Systems](https://arxiv.org/abs/2607.28629v1)（Roumeliotis / Sapkota）：[取得できた本文](https://www.researchgate.net/publication/411138539_OpenClaw_and_Ollama_in_Agentic_AI_Toward_Fully_Autonomous_and_Scalable_AI_Agent_Systems)の2〜4節を確認。推論・ランタイム・実行・メモリ・ガバナンスを分離しています。実験はホスト上で動作し、コンテナ隔離の実証ではありません。
- [著者のコード・評価資料](https://github.com/Applied-AI-Research-Lab/OpenClaw-and-Ollama-in-Agentic-AI)：現在は入力情報を揃えた対照条件やメモリ漏洩補正が追加されています。取得できた本文の小規模実験と混ぜず、再現時はcommitを固定します。
- [Accelerating Post-Quantum Cryptography via LLM-Driven Hardware-Software Co-Design](https://arxiv.org/html/2602.09410v1)（Liao / Adegbija / Lysecky）：プロファイル解析の進め方を参照。Ollama Workerの能力を検証した論文ではありません。

以下は**本プロジェクト独自の応用案**です。「毎ターンのJSON Memory Anchor」は確認した本文で見つからなかったため、論文の手法として扱いません。モデル規模に依存しないという証明や、コーディング成功率の改善保証もありません。

### 改善候補と完了条件

| 優先度 | 改善案 | 採用前に必要な確認 |
|---|---|---|
| P1 | 既存Workerの責任境界を整理。Ollamaは型付きアクションを提案し、信頼された制御側が状態・認可・期限・コマンド実行を管理する | 許可外のコマンド・パス・権限変更を拒否し、実行操作を登録済み操作IDと実際の結果に対応づける |
| P1 | バージョン付き状態チェックポイントを検討。タスク/要件版、目標、候補差分digest、適用時のTDD段階、直近の独立検証結果、次に許された操作ID、残予算を保持する | 古い・破損した・別タスクの状態では証拠を再利用できない。再開で予算をリセットせず、不明な副作用を照合してから再試行する。文書修正に架空のRED証拠を要求しない |
| P2 | まずタスク内メモリを扱い、タスク間メモリには出典・有効期限・適用範囲を持たせる。取得内容は信頼されない入力とする | 目標の維持、古い要件、汚染メモ、タスク間混入を評価。メモリから認可・承認・受け入れテストを書き換えられない |
| P2 | 同じモデル・入力・予算で、現行Worker、永続化なし、永続化あり、必要なら構造化チェックポイントありを比較する | 隔離と独立した正解判定を揃え、成功・実際のツール効果・復旧・範囲逸脱・遅延・再試行・コストを失敗も含めて記録。RESULTの自己申告だけで合格にしない |
| P3 | ローカルモデルによるソース/性能ログ要約を試す。関数の参照先と実測根拠を併記する | ソースだけの予測は実測結果を隠して評価。ビルド・コンパイラ・負荷条件と順位一致を記録し、未測定値は不明とする。FPGAやクラウドの導入を自動推奨しない |

### 既存構成との接続

[既存のFactory連携](factory-integration.md)を基礎にします。Leadが範囲を決め、Sidekickが候補を作り、AI Governance Controlが独立検証し、人がPRを確認します。ネイティブadapterやOpenClaw依存の採用は別の検討です。論文を参照しただけでランタイム導入済み・新プロトコル対応済みとはしません。

**次の調査目標：** チェックポイント契約と少数の固定オフライン実装・復旧タスクを定義し、構成変更の前に再現可能なベースラインを残します。
