#!/usr/bin/env bash
# fetch_bugsinpy_patch.sh — Download a BugsInPy bug_patch.txt from GitHub.
#
# Usage:
#   ./fetch_bugsinpy_patch.sh <problem_id> [output_dir]
#
# Example:
#   ./fetch_bugsinpy_patch.sh httpie-1 /tmp/patches
#   # → downloads to /tmp/patches/projects/httpie/bugs/1/bug_patch.txt
#
# If no output_dir is given, prints the patch to stdout.

set -euo pipefail

GITHUB_RAW_BASE="https://raw.githubusercontent.com/soarsmu/BugsInPy/master"

usage() {
    echo "Usage: $0 <problem_id> [output_dir]"
    echo "  problem_id: format '{project}-{number}', e.g. httpie-1, youtube-dl-3"
    echo "  output_dir: optional directory to save the patch (creates BugsInPy structure)"
    exit 1
}

if [[ $# -lt 1 ]]; then
    usage
fi

PROBLEM_ID="$1"
OUTPUT_DIR="${2:-}"

# Parse problem_id: split on last hyphen.
# e.g. "youtube-dl-1" → project="youtube-dl", number="1"
NUMBER="${PROBLEM_ID##*-}"
PROJECT="${PROBLEM_ID%-*}"

if [[ -z "$PROJECT" || -z "$NUMBER" || ! "$NUMBER" =~ ^[0-9]+$ ]]; then
    echo "Error: Invalid problem_id format: '$PROBLEM_ID'" >&2
    echo "Expected format: {project}-{number} (e.g. httpie-1, youtube-dl-3)" >&2
    exit 1
fi

URL="${GITHUB_RAW_BASE}/projects/${PROJECT}/bugs/${NUMBER}/bug_patch.txt"

if [[ -n "$OUTPUT_DIR" ]]; then
    DEST_DIR="${OUTPUT_DIR}/projects/${PROJECT}/bugs/${NUMBER}"
    mkdir -p "$DEST_DIR"
    DEST_FILE="${DEST_DIR}/bug_patch.txt"
    
    if curl -fsSL "$URL" -o "$DEST_FILE"; then
        echo "Downloaded: $DEST_FILE"
    else
        echo "Error: Failed to download patch for '$PROBLEM_ID'" >&2
        echo "URL: $URL" >&2
        exit 1
    fi
else
    # Print to stdout
    if ! curl -fsSL "$URL"; then
        echo "Error: Failed to download patch for '$PROBLEM_ID'" >&2
        echo "URL: $URL" >&2
        exit 1
    fi
fi
