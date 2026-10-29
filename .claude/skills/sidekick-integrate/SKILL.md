---
name: sidekick-integrate
description: `sidekick integrate` によるグローバル設定(~/.claude/settings.json 等)の変更手順を案内する。人専用。
when_to_use: TRIGGER when: ユーザーが明示的に /sidekick-integrate を実行したとき。 SKIP: AI の判断での呼び出し全般。グローバル設定の自動変更。
disable-model-invocation: true
---

# sidekick-integrate (MANUAL_ONLY)

グローバル設定を変更するため、AI は実行しない。人が自分で実行する。

1. まず変更内容の確認: `python -m sidekick.cli integrate --global --dry-run`
2. 状態の確認: `python -m sidekick.cli integrate --global --status`
3. 内容を確認した人が、自分で `--dry-run` を外して実行する。
4. 元に戻すときは `--remove`(この統合が書いた項目だけを削除する)。
