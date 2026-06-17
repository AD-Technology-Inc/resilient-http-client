---
name: github-issues
description: Use this skill whenever work should be selected from GitHub issues, tasks need tracking, or an autonomous agent is processing repository issues.
---

# GitHub Issues Skill

## Purpose

Process repository issues one at a time in a predictable and repeatable manner.

## Workflow

### 1. Fetch Issues

Retrieve all open GitHub issues.

Ignore:

* closed issues
* duplicate issues
* blocked issues
* issues already marked completed
* issues already marked in_progress

### 2. Select Issue

Choose exactly one issue.

Priority order:

1. high priority
2. oldest open issue
3. smallest independent issue

### 3. Start Task

Create or update task tracking.

Mark issue status:

in_progress

Record:

* issue number
* title

### 4. Implement

Implement only the changes necessary to satisfy the issue.

Avoid unrelated refactoring.

Follow existing project conventions.

### 5. Testing

Add or update tests if required.

Run formatting.

Run the complete test suite.

### 6. Failure Handling

If tests fail:

1. investigate
2. fix
3. rerun tests

Maximum attempts: 3

If still failing:

Create:

.agent-stuck

Contents:

Issue #<number>
Reason: <explanation>

Mark task:

stuck

Stop execution.

### 7. Success Handling

Commit changes:

ISSUE #<number>: <short description>

Mark task:

completed

### 8. Completion

If no issues remain:

Create:

.agent-complete

Exit successfully.

## Rules

* Work on exactly one issue.
* Never skip testing.
* Never skip formatting.
* Never create both `.agent-complete` and `.agent-stuck`.
* Prefer small reviewable commits.
