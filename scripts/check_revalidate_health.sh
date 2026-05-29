#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="/home/adriantd/Projects/llm-autofix-agents"
cd "$REPO_ROOT"

latest_log="$(ls -t results/revalidate-*.log 2>/dev/null | head -1 || true)"

session_alive=0
if tmux has-session -t revalidate 2>/dev/null; then
  session_alive=1
fi

oauth_errors=0
fatal_errors=0
if [[ -n "${latest_log}" ]]; then
  oauth_errors=$(grep -ci "No authentication information found\|oauth" "$latest_log" || true)
  fatal_errors=$(grep -ci "\[validación\] FALLO" "$latest_log" || true)
fi

# Healthy if: running or completed without OAuth errors.
healthy=0
if [[ $session_alive -eq 1 && $oauth_errors -eq 0 ]]; then
  healthy=1
elif [[ -n "${latest_log}" ]] && grep -q "Re-validación finalizada" "$latest_log" && [[ $oauth_errors -eq 0 ]]; then
  healthy=1
fi

if [[ $healthy -eq 1 ]]; then
  exit 0
fi

set -a
source .env
set +a

python3 - <<'PY'
import os
import httpx

topic = os.environ.get("NTFY_TOPIC", "")
if not topic:
    raise SystemExit(0)

msg = "Revalidación con posible problema: revisar tmux 'revalidate' y logs (OAuth/FALLO detectado o sesión caída)."
headers = {"Title": "TFM Revalidacion ALERTA".encode("utf-8").decode("latin-1"), "Priority": "5", "Tags": "warning,no_entry"}
httpx.post(f"https://ntfy.sh/{topic}", content=msg.encode("utf-8"), headers=headers, timeout=10)
PY
