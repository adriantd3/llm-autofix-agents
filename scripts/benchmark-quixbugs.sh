#!/usr/bin/env bash
# benchmark-quixbugs.sh
# Runs the 4 QuixBugs architecture benchmarks sequentially, then aggregates results.
# Usage: bash scripts/benchmark-quixbugs.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

BATCHES=(
  "batches/quixbugs-mono-local.yaml"
  "batches/quixbugs-handoff-local.yaml"
  "batches/quixbugs-orchestrator-local.yaml"
  "batches/quixbugs-planner-executor-local.yaml"
)

RUN_IDS=()

echo "============================================"
echo "  QuixBugs benchmark — 4 architectures"
echo "  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "============================================"

# Verify Ollama is reachable before starting
if ! curl -sf http://localhost:11500/v1/models > /dev/null 2>&1; then
  echo "ERROR: Ollama not reachable at http://localhost:11500. Aborting."
  exit 1
fi
echo "Ollama OK."
echo ""

for BATCH_CONFIG in "${BATCHES[@]}"; do
  ARCH=$(grep "^  architecture:" "$BATCH_CONFIG" | awk '{print $2}')
  echo "--------------------------------------------"
  echo "Running: $BATCH_CONFIG  (arch=$ARCH)"
  echo "Start: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "--------------------------------------------"

  BATCH_CONFIG="$BATCH_CONFIG" make batch

  echo "Done:  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo ""
done

# Aggregate results from all quixbugs batch dirs produced today
TIMESTAMP_PREFIX="$(date -u '+%Y%m%d')"
BATCH_DIRS=$(find results -maxdepth 1 -type d -name "batch-quixbugs-*${TIMESTAMP_PREFIX}*" | sort)

if [[ -z "$BATCH_DIRS" ]]; then
  echo "No batch dirs found for today — trying broader glob..."
  BATCH_DIRS=$(find results -maxdepth 1 -type d -name "batch-quixbugs-*" | sort)
fi

OUT="results/quixbugs-benchmark-$(date -u '+%Y%m%dT%H%M%SZ').db"

echo "============================================"
echo "Aggregating into: $OUT"
echo "Batch dirs:"
echo "$BATCH_DIRS"
echo "============================================"

# shellcheck disable=SC2086
uv run python -m llm_autofix_agents.observability.aggregate --out "$OUT" $BATCH_DIRS

echo ""
echo "Aggregate DB: $OUT"
echo ""
echo "Quick summary per architecture:"
uv run python - <<'PYEOF' "$OUT"
import sys
import sqlite3

db = sys.argv[1]
con = sqlite3.connect(db)

rows = con.execute("""
    SELECT
        batch_id,
        COUNT(*) AS total,
        SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS successes,
        SUM(CASE WHEN status='partial' THEN 1 ELSE 0 END) AS partial,
        SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) AS errors,
        ROUND(AVG(iterations_used), 2) AS avg_iters,
        ROUND(AVG(total_tool_calls), 2) AS avg_tools,
        ROUND(AVG(elapsed_seconds), 1) AS avg_secs
    FROM runs
    GROUP BY batch_id
    ORDER BY batch_id
""").fetchall()

if not rows:
    print("No rows found in the aggregate DB.")
    sys.exit(0)

header = f"{'batch_id':<55} {'total':>5} {'ok':>5} {'part':>5} {'err':>5} {'fix%':>6} {'avg_it':>7} {'avg_tc':>7} {'avg_s':>7}"
print(header)
print("-" * len(header))
for r in rows:
    batch_id, total, ok, part, err, avg_it, avg_tc, avg_s = r
    fix_pct = round(100.0 * (ok or 0) / total, 1) if total else 0
    print(f"{batch_id:<55} {total:>5} {ok or 0:>5} {part or 0:>5} {err or 0:>5} {fix_pct:>5.1f}% {avg_it or 0:>7} {avg_tc or 0:>7} {avg_s or 0:>7}")

con.close()
PYEOF

echo ""
echo "Benchmark complete."
