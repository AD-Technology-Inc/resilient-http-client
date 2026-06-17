# Issue Worker

## Goal

Complete one issue at a time.

## Instructions

1. Use github-issues skill to fetch open issues.
2. Check existing Tasks and skip issues already completed or in_progress.
3. Pick the most appropriate remaining issue.
4. Create a Task and mark it in_progress.
5. Implement the fix or feature.
6. Add tests if needed.
7. Run formatting.
8. Run the full test suite.

If tests fail:
- attempt fixes
- after 3 failed attempts mark the Task stuck
- create .agent-stuck with issue number and reason

If no issues remain:
- create .agent-complete
- exit

Commit changes:
ISSUE #<number>: <short description>

Mark the Task completed.