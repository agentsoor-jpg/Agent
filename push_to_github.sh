#!/bin/bash
# Run this in the Replit Shell to push to GitHub
# Usage: bash push_to_github.sh

set -e

REPO_URL="https://agentsoor-jpg:${GITHUB_PERSONAL_ACCESS_TOKEN}@github.com/agentsoor-jpg/Agent.git"

echo "=== Step 1: Current status ==="
git status

echo ""
echo "=== Step 2: Recent local commits ==="
git log --oneline -3

echo ""
echo "=== Step 3: Fetching from GitHub ==="
git fetch "$REPO_URL" main:refs/remotes/github/main

echo ""
echo "=== Step 4: Merging remote changes ==="
git merge refs/remotes/github/main --no-edit --strategy-option=ours --allow-unrelated-histories || {
    echo "Clean merge (no conflicts)"
}

echo ""
echo "=== Step 5: Pushing to GitHub ==="
git push "$REPO_URL" main

echo ""
echo "=== Step 6: Verify ==="
git log --oneline -3
echo ""
echo "DONE — check https://github.com/agentsoor-jpg/Agent"
