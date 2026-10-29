---
name: delegation-background
description: Lead / Worker 委任ワークフローの背景知識。ユーザーが直接呼ぶ必要はない。
when_to_use: TRIGGER when: 委任の可否や TASK の書き方、Worker ロールの制約を確認するとき。 SKIP: 委任の実行そのもの。
user-invocable: false
---

# delegation-background

方針の正本は `.ai/DELEGATION.md`。ここには複製しない。

- Worker ロールは command-runner / code-explore / spec-coder。
- code-explore はコマンドを実行できず、既存ファイルのみを対象にする。
- `AGENTS.md`、`CLAUDE.md`、`.ai/`、`.claude/` などは Allowed Files に指定できない。
- 詳細は `.ai/DELEGATION.md` と `src/sidekick/role_contract.py` を読む。
