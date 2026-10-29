---
name: task-review
description: Lead 向けに、Worker が返した RESULT.md と差分を読み取り専用でレビューする。
when_to_use: TRIGGER when: 「RESULT をレビュー」「Worker の結果を確認」「委任結果の点検」など、委任結果の確認を求められたとき。 SKIP: 修正の実装、コマンド実行、TASK の作成。
allowed-tools: Read, Grep, Glob, AskUserQuestion
---

# task-review

読み取り専用。ファイルは変更しない。

1. `.ai/DELEGATION.md` と `.ai/RULES.md` を読み、Lead のレビュー責務を確認する。
2. `.ai/RESULT.md` と対象差分を読む。
3. 各所見に `ファイルパス:行番号` の根拠を付け、PASS / FAIL / 判断不能で報告する。
4. Worker が主張した検証が実行された証拠(コマンド出力)があるか確認し、なければ「未確認」と書く。
