# Modal GPU experiments / 必要な時だけ使うGPU実験場

[Documentation index](README.md) | [RTX 3070の用途比較](future-directions.md) | [現在の検証範囲](current-status.md)

確認日: **2026-11-05**。この文書は運用方針と実験案です。Modal adapter、GPU実行、デプロイ、モデル取得、認証・支払設定を実装・実施した証拠ではありません。

## 役割分担

- **普段はローカル RTX 3070:** 小さな分類・抽出、検索補助などをCPUや既存クラウドAIとも比較する。外へ出せないデータはローカルに残す。
- **Modalは単発のGPU実験場:** ローカルのVRAMに収まらない候補や、同一の公開・合成入力での推論比較を、必要な時だけ実行する候補。ローカルの常用環境を移設する計画ではない。
- **KaggleはNotebook内の学習・評価候補:** 利用可能な枠と規約の範囲で使う。常設推論APIや遠隔PCの代替にはしない。

この設計判断はSidekickに置きます。HomeLabの監視・日常運用とは分け、既存WorkerをModalへ自動転送する機能は追加しません。Gemmaの導入予定や現在のQwen利用報告も変更しません。

## 最初の実験を小さく決める

1. [GPU不要の基準作り](future-directions.md#1-gpu不要で基準を作る最初に推奨)を先に行う。公開可能な合成入力、採点方法、成功・中止条件を固定する。
2. モデルとライセンス、revision / digest、量子化、入力長、出力上限、batchを固定する。ローカルで困る理由を一つだけ記す。
3. Modalでは必要なVRAMに合うGPUを明示し、まず単一GPU・単一Function・単一実行を計画する。高価なGPUや別GPUへの自動fallbackは既定にしない。[GPU指定](https://modal.com/docs/guide/gpu)
4. 起動・重み読込・推論・結果取得を別々に測る。同じモデルが両方で動く場合のみ速度を直接比較する。別モデルの場合は品質と総費用の比較として区別する。
5. 結果保存後、稼働中App / containerと使用量を確認して終える。採用判断は品質、待ち時間、人の修正時間、総費用、運用の手間で行う。GPUを使わない結論も可。

## 実行前の費用ガード

以下は将来の実験で満たす条件であり、この文書による課金・設定変更の承認ではありません。

- **予算が未確定なら実行しない。** Provider、実験対象、USDの総上限、単発であること、送信データ、最大時間・件数・再試行数を実行前に確認する。無料枠も自動実行の許可とは扱わない。
- **Workspace budgetとspend limitを区別する。** 前者はcredit適用前のusage上限、後者は適用後の自己負担上限。未設定時のspend limitは無料枠内に止まる保証ではない。現在の画面と公式説明で両方を確認する。Environment budgetはTeam / Enterprise向けでcomputeのみのため、請求全体のガードにはしない。[Budgets](https://modal.com/docs/guide/budgets)
- **計画上は並列1・常駐0。** `max_containers=1`、`min_containers=0`、`buffer_containers=0`を候補とし、短い`scaledown_window`を明示する。これらはFunctionごとの設定で、他Function・別Appを含む金額上限ではない。[Scaling](https://modal.com/docs/guide/scale)
- **timeoutだけで総費用を制限しない。** `timeout`は実行試行ごとで、起動には`startup_timeout`が別にある。再試行は初回実験では追加しない方針とし、総入力件数・総壁時計時間にも中止条件を置く。[Timeouts](https://modal.com/docs/guide/timeouts)
- cron、公開Web endpoint、常駐container、並列map、無制限retryは初回対象外。OOMや上限到達時は停止して記録し、GPU増強や予算拡大を自動で行わない。
- 支払方法や認証の設定・保存、権限変更、データuploadは別途必要な承認を得る。予算の表示だけで実行済みの使用量が消えるとは考えない。[Billing](https://modal.com/docs/guide/billing)

### 料金の読み方（2026-11-05の公開表示）

公式[Modal pricing](https://modal.com/pricing)では、通常GPU TasksのT4が **$0.000164/秒**、L4が **$0.000222/秒**、A10が **$0.000306/秒**。例としてL4を600秒使うGPU部分は **$0.1332**（0.000222 × 600）です。これは総額・見積保証・承認済み予算ではありません。

CPU、メモリ、保存領域、転送、起動・読込、scale-downまでの待機も確認します。地域指定・非preemptible等の条件で変わり得ます。Starterの公開表示は月$30 creditですが、個別アカウントの対象・残額・期限を示しません。単価・適用credit・実際の設定を実行直前に再確認し、credit差引前のusageと最終請求を分けて記録してください。

## Kaggleの境界

公式[Notebooks](https://www.kaggle.com/docs/notebooks)と[GPU usage guide](https://www.kaggle.com/docs/efficient-gpu-usage)に従い、実行画面のGPU提供状況・週次quota・セッション上限を毎回確認します。公開ガイドの時間数やGPU型番を恒久的保証にしません。終了時はセッションを止めます。

このプロジェクトでは、公開API化、SSH/トンネルによる常用サーバー化、keep-aliveでの延命、複数アカウント等によるquota回避は行いません。これは保守的なプロジェクト方針であり、全項目について規約条文を確認済みという意味ではありません。[Terms of Use](https://www.kaggle.com/terms)の本文は今回の取得では読めなかったため、実行前に現行規約と各dataset / competitionの条件を直接確認し、不明なら実行を止めます。

## 記録と公開範囲

実験結果には日付、repo commit、SDK / runtime、モデルrevision、GPU、設定、入力件数、実行ID、起動・推論時間、品質、失敗、usageと費用の対象範囲を残します。未実行の欄は「未実行」とし、クラウド上で動いたことをローカル実機の検証と混同しません。

公開repoに置くのは公開・合成入力と匿名の再現条件だけです。私的会話、実運用ログ、API token、アカウント識別子、個人のcredit残額・請求書・billing画面は置きません。モデルの利用条件や入力の外部送信許可を確認できない場合、ModalにもKaggleにも送りません。
