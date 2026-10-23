# Worker role roadmap / Worker の役割分離計画

Date / 記録日: **2026-10-15**

Status: **Candidate role paths implemented 2026-10-23; live validation and log retention remain open**

## 目的と出典

親のクラウド AI に返す情報を短くしつつ、実行の事実・調査の根拠・実装の未完了を確認しやすくする。モデルを先に変更するのではなく、既存 Worker の仕事・権限・報告契約を役割ごとに絞る。

参考: okkun0524 / GENDA、[Haiku 5.5 を機に Sonnet 以下で動かしていたサブエージェントを見直した](https://zenn.dev/genda_jp/articles/haiku-5-5-subagent-roles)（2026-10-08 公開、2026-10-15 参照）。実行結果の圧縮、根拠付き調査、仕様が固まった実装という区分を設計の参考にした。以下は Sidekick 向けの応用案であり、記事の実験の再現結果ではない。記事の Haiku 比較結果を Ollama の速度・品質・費用効果の保証に使わない。

## 現行設計との接続

- [Architecture](architecture.md)、[委任方針](../.ai/DELEGATION.md)、[Permanent Rules](../.ai/RULES.md) を基盤とする。`LOCAL / LEAD / BLOCKED` は委任判断であり、新しい role はその判断を置き換えない。Lead が要件・設計・安全判断・最終レビューを持ち、Worker は承認済みの範囲だけを実行する。
- role は既存の TASK / RESULT、Watcher、Runner、安全検査に段階的に追加する案。新 daemon、多段オーケストレーション基盤、新モデルの導入は必要条件にしない。未対応 role を既存実装経路へ黙って流さず、契約不備・仕様の曖昧さは Lead に戻す。
- Allowed Files / Commands、パス制約、出力の秘密情報対策、diff guard、secret scan、Git の境界を維持する。role は権限を広げる手段ではない。自動 push の既定値や人の merge 権限も変えない。
- [AI Governance Control の独立検証](factory-integration.md)は維持する。Worker の報告やローカルでの合格だけでは独立した合格証拠にならない。

## 現行コードの静的観察

確認基準: `309a0dc`（参照時の main）。対象は [runner.py](../src/sidekick/runner.py) と [workspace.py](../src/sidekick/workspace.py)。以下は読解による観察であり、再現試験は実施していない。

1. `SidekickRunner._run_verification_suite` は stdout / stderr を `test_summaries` に格納し、`execute` が `test_results` に連結する。`_write_result` はそれを RESULT の Test Results に出す。現在も `WorkspaceManager.run_command` の出力サニタイズは通るが、長いコマンド出力が報告に入る経路がある。
2. `_run_verification_suite` は `all_passed = True` で開始するため、空の検証列では実行なしでも true を返す。`execute` には、その戻り値から `SUCCESS` になる経路がある。仕様上許容すべきケースかは未判断で、確定バグとは扱わない。実装完了と検証状態を別々に記録する検討事項とする。
3. `_explore_repository` は許可ファイルをサイズ・コンテキスト制限内でまとめて読み、その後は実装用 JSON の `files_to_write` を適用する共通経路になっている。role 名を追加するだけでは読取調査専用にならない。読取・検索操作、専用出力、編集・Git 操作の拒否を実行側で分離する設計が必要。

## 提案する役割と報告契約

### command-runner: 許可済みコマンドの実行と短い報告

Lead が指定した許可済みの非対話コマンドだけを信頼された Python ランタイムで実行する。モデルがコマンドや権限を増やすことはできない。テスト・lint・型確認・ビルド等を対象候補とし、deploy / apply / push や入力待ちの操作は対象外とする。

実行有無、終了コード、timeout、合否はランタイムが観測・判定する。AI は必要なログ要約だけを補助し、結果を書き換えない。終了コード 0 でもテスト 0 件なら無条件に合格としない。ツール別の件数・合格条件を定義し、判定できない場合は未検証のまま返す。

親へ返す契約案:

| 項目 | 内容 |
| --- | --- |
| Identity | task ID、対象 candidate / diff digest、実行 ID |
| Command | 承認されたコマンド、CWD、開始・終了時刻、所要時間 |
| Execution | `RAN / DID_NOT_RUN / TIMED_OUT / NOT_APPLICABLE` と理由 |
| Verification | `PASSED / FAILED / UNVERIFIED / NOT_APPLICABLE` と観測根拠 |
| Outcome | 終了コード（未起動時は null）、件数、最初の失敗箇所、未実行項目 |
| Evidence | ローカルログ参照、短いサニタイズ済み要約、切り詰めの有無 |

対象外は Lead が理由を承認した場合に限り、未実行を合格や対象外へ自動変換しない。依存不足・起動失敗・途中停止も明示する。

詳細ログはローカルに保持し、親へは短い構造化結果を返す。保存先・参照権限・保持期間・秘密情報の除去・長さ上限は実装前に決める。ログを共有・commit する場合も既存の秘密情報対策を適用する。

**コマンド実行は OS レベルの読取専用ではない。** テストやビルドはファイル生成、アプリコード実行などの副作用を持つ。許可リストは隔離の保証ではなく、[SECURITY.md](../SECURITY.md) のホスト実行境界を維持する。必要な隔離と独立検証を省略しない。

### code-explore: 根拠を追える読取調査

承認済みの範囲に対する読取・検索だけを提供する。編集、実装 JSON の適用、任意コマンド、Git の変更・commit・push を実行側で禁止する。プロンプトの「読取専用」だけに依存しない。

報告は結論、根拠（実際に読んだ `file:line` と事実）、根拠を超える推論、検索パターンと範囲、未読・未確認・上限で省略した範囲を分ける。「存在しない」等の否定には検索範囲と限界を必須にする。親が根拠を抜き取り確認できる形にし、重要判断は Lead が裏取りする。短縮のために未確認事項を落とさない。

### spec-coder: 設計済みの小変更

Lead が仕様・許可ファイル・受け入れ条件・検証コマンドを決めた小変更だけを扱う。設計判断、仕様と既存コードの矛盾、範囲拡大が必要になった場合は Lead に戻す。

変更概要とファイル、要求仕様との差分、未実施項目、未検証項目、実行証拠を報告する。モデルの「完了」とランタイムの検証結果を分離し、検証省略を成功へまとめない。既存の独立検証と最終 diff レビューを維持する。

## 導入順と採用前の確認

順番は調査・導入の優先度であり、リリース日や実装済み機能を表さない。

| 順番 | 改修候補 | 採用前に確認すること |
| --- | --- | --- |
| 1 | command-runner と報告圧縮。実装状態と検証状態を分離 | 正常終了、非ゼロ終了、未起動、0 件、空検証列、timeout、途中で停止した後続項目、対象外を区別できる。要約の省略が合否を変えず、ログから追跡でき、未許可コマンドを実行できない |
| 2 | code-explore の専用読取・検索経路と報告 | 引用根拠の正確性、推論との区別、否定の検索範囲、コンテキスト上限を確認できる。編集と Git 変更は実行側で拒否する |
| 3 | spec-coder の小変更契約 | 曖昧さ・仕様差分を Lead へ戻し、未実施・未検証を残せる。許可範囲を超える変更と未検証の成功扱いを防ぐ |

まず同じ Ollama モデル・入力・課題・予算・受け入れ基準で、現行経路と各改修候補を比較する。小さな固定課題に失敗ケースも含め、クラウドの入出力 token、ローカル実行時間、再試行数、独立判定による成功率を記録する。報告サイズ、根拠の誤り・抜け、範囲違反も確認する。token の削減だけで採用せず、品質や待ち時間の悪化も含めて判断する。

役割分割の効果を確認してから、モデル選定を別の判断として扱う。今回の文書追記には製品実装、製品テスト実行、モデル導入を含めない。今後の非設計作業は既存の Claude / Antigravity への委任方針に従い、今回の計画が自動で実装や Watcher 起動を許可することはない。

## English summary

**2026-10-23 candidate update:** Explicit roles now dispatch through distinct
runtime paths. `command-runner` observes approved commands without a model or
Git automation, but does not retain detailed logs. `code-explore` uses a
bounded read-only source path and validates cited line excerpts. `spec-coder`
checks the entire model edit batch before writing and records implementation
separately from verification. Empty suites, timeouts, blocked commands and
zero-test output do not yield `SUCCESS`. See the [role guide](worker-roles.md)
and [security audit candidate](security-audit.md). Synthetic tests pass; real
Ollama/GPU behavior and independent task success remain unverified.

**2026-10-15 proposal and acceptance criteria.** Inspired by the GENDA article linked above, specialize the existing Worker rather than replacing the Lead/Worker architecture. Preserve `LOCAL / LEAD / BLOCKED`, all file/command/Git guards, and AI Governance Control's independent verification. No new daemon or multi-stage orchestration platform is required.

1. Start with **command-runner**: trusted Python executes only approved commands, observes execution and verification separately, retains detailed logs locally, and returns a compact structured report. Distinguish ran, did not run, timeout, passed, failed, unverified and justified not-applicable cases. Command execution can have test/build side effects; it is not OS-level read-only isolation.
2. Add **code-explore**: enforce read/search-only capabilities in the runtime, denying edits and Git mutations. Separate cited facts, inferences, search scope and uncovered areas; Lead checks evidence before relying on it. A role label alone cannot turn today's bulk allowed-file reading and implementation-JSON path into a read-only explorer.
3. Define **spec-coder** for small changes with settled specifications. Escalate ambiguity and report specification deviations, unfinished work and unverified claims separately from implementation completion.

Static inspection at `309a0dc` found command output flowing into RESULT and a path to `SUCCESS` with an empty verification suite. Neither observation has been reproduced here; whether empty verification is acceptable remains undecided. They motivate explicit result contracts, not a confirmed bug claim.

Compare the current and proposed paths using the same model, inputs, budgets and acceptance oracle first. Measure cloud input/output tokens, local elapsed time, retries and independently assessed success, including failures. The article's Haiku observations do not guarantee Ollama performance. Model changes and product implementation are separate future decisions; this document does not authorize them.
