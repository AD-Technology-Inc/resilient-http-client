#!/usr/bin/env bash

set -euo pipefail

#-------------------------
# Config
#-------------------------
ITERATIONS="${1:-10}"

MAIN_BRANCH="${MAIN_BRANCH:-main}"
BRANCH="${BRANCH:-overnight-batch-$(date +%Y%m%d-%H%M%S)}"

PROMPT_FILE=".gemini/prompts/issue-worker.md"

SUCCESS_FILE=".agent-complete"
STUCK_FILE=".agent-stuck"

#-------------------------
# Helpers
#-------------------------
cleanup() {
    rm -f "$SUCCESS_FILE" "$STUCK_FILE"
}

trap cleanup EXIT

#-------------------------
# Validate
#-------------------------
if ! command -v gemini >/dev/null 2>&1; then
    echo "gemini command not found."
    exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI (gh) is not installed. Please install it to use this agent."
    exit 1
fi

if [ ! -f "$PROMPT_FILE" ]; then
    echo "Prompt file missing: $PROMPT_FILE"
    exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "Working directory is dirty. Commit or stash changes first."
    exit 1
fi

#-------------------------
# Setup
#-------------------------
git checkout "$MAIN_BRANCH"
git pull origin "$MAIN_BRANCH"

git checkout -b "$BRANCH"

echo "Branch: $BRANCH"
echo "Iterations: $ITERATIONS"
echo "Prompt: $PROMPT_FILE"

#-------------------------
# Agent Loop
#-------------------------
for ((i=1; i<=ITERATIONS; i++)); do

    echo
    echo "=== Iteration $i/$ITERATIONS ==="

    if ! timeout 5m gemini -p "$(cat "$PROMPT_FILE")"; then
        echo "Gemini timed out"
        exit 1
    fi

    if [ -f "$STUCK_FILE" ]; then
        echo "Agent stuck:"
        cat "$STUCK_FILE"
        exit 1
    fi

    if [ -f "$SUCCESS_FILE" ]; then
        echo "All tasks completed."
        break
    fi

done

#-------------------------
# Push
#-------------------------
git push -u origin "$BRANCH"

echo
echo "Finished."
echo "Review:"
echo "git log $MAIN_BRANCH..$BRANCH"