# Local AI Sidekick

[English](README.md) | [日本語](README.ja.md)

**強力なクラウドAIを主役に、手元の NVIDIA RTX 3070 を補助役として活かす方法を探すプロジェクトです。** Claude・Gemini・ChatGPT などと組み合わせながら、ローカルGPUに任せる意味のある仕事を試行錯誤しています。

- **いま試していること:** 本人の申告では、ローカルで Qwen を動かしています。モデルの詳細や、このリポジトリの各機能がGPUで実運用できたかは別の確認事項です。
- **このrepoにあるもの:** Ollama を使う coding Worker、範囲を決めた委譲、TASK / RESULT、Git制御、役割別の実行経路、合成ログを使うオフライン監査の候補実装。コード・合成テストの存在と実機運用の実績は区別します。
- **未実装・今後:** 短い分類・抽出、ローカル検索の補助、音声文字起こしなどを比較予定。各クラウド製品との接続も、実装や検証の有無を確認しながら探ります。coding offload は用途候補の一つです。

当初はクラウドAIのトークン節約を重視していました。いまの自分の使い方では、クラウド側に任せてどんどん作れる場面が増えたので、ローカルに任せる理由を考え直しています。クラウドが常に安い・速いという主張ではありません。

[![CI](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml/badge.svg)](https://github.com/moruku36/local-ai-sidekick/actions/workflows/ci.yml)

## 読むところ

| 知りたいこと | 文書 |
| --- | --- |
| 現在の機能と確認できた範囲、連携の限界 | [現在の実装・検証範囲](docs/current-status.md) |
| RTX 3070 の用途比較と次に試すこと | [今後の展開案](docs/future-directions.md) |
| GPUを使わない確認、Workerの設定・運用 | [短い導入ガイド](docs/usage.md) / [詳細ガイド](docs/usage.ja.md) |
| 文書一覧とフォルダ構成 | [docs入口](docs/README.md) |

## 既存Workerの位置づけ

```text
ユーザー + Lead AI -> 範囲を決めたタスク -> ローカルWorker -> 結果と差分 -> Lead / 人のレビュー
```

要件・設計・安全判断・最終レビューはLeadが持ちます。Workerは許可ファイルとコマンドに制約がありますが、ホスト上のコマンド実行は完全なsandboxではありません。Git自動化は任意、pushは既定OFF、自動mergeは未対応です。[安全上の境界](SECURITY.md)も参照してください。

Windows Defenderの単純な状態収集にGPUは不要です。HomeLab側の運用と、このrepoの合成ログ監査候補は分けて扱います。

## ライセンス

[MIT](LICENSE)。
