# Current Task

## Goal
Implement a mathematical utility function to compute factorial and verify directory exploration.

## Background
We need factorial computation in src/math_utils.py.
Directory exploration should automatically discover src/ and tests/ directories.

## Allowed Files
- src/
- tests/

## Forbidden Operations
- Do not modify files outside Allowed Files
- Do not execute unlisted commands

## Requirements
- Add `factorial(n: int) -> int` in `src/math_utils.py`.
- Handle n = 0 returning 1. Raise ValueError on negative n.
- Add unit tests in `tests/test_math_utils.py`.

## Acceptance Criteria
- `python -m unittest discover tests` succeeds with 0 exit code.

## Allowed Commands
- python -m unittest discover tests

## Review Points
- Recursion or loop safety and input validation
