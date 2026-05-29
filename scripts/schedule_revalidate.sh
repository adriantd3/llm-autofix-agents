#!/bin/bash
# Script para arrancar la revalidación a las 22:10 UTC

REPO_ROOT="/home/adriantd/Projects/llm-autofix-agents"
TARGET_TIME="22:10"

cd "$REPO_ROOT"

# Calcular segundos hasta las 22:10 UTC
current_hour=$(date -u +%H)
current_min=$(date -u +%M)
target_hour=22
target_min=10

current_total_min=$((current_hour * 60 + current_min))
target_total_min=$((target_hour * 60 + target_min))

# Si ya pasó las 22:10 hoy, programar para mañana
if [ $current_total_min -ge $target_total_min ]; then
    wait_min=$((1440 - current_total_min + target_total_min))
else
    wait_min=$((target_total_min - current_total_min))
fi

wait_sec=$((wait_min * 60))

echo "================================================================"
echo "  Revalidación programada para las $TARGET_TIME UTC"
echo "  Hora actual: $(date -u +%H:%M) UTC"
echo "  Espera: $wait_min minutos ($wait_sec segundos)"
echo "================================================================"

# Esperar
sleep $wait_sec

# Enviar notificación de inicio
set -a
source .env
set +a

uv run python3 -c "
import httpx, os
topic = os.environ.get('NTFY_TOPIC', '')
r = httpx.post(f'https://ntfy.sh/{topic}',
    content='🚀 Revalidación iniciada automáticamente a las 22:10 UTC - claude-sonnet-4.5, wait=300s'.encode('utf-8'),
    headers={'Title': 'TFM Revalidacion INICIADA'.encode('utf-8').decode('latin-1'), 'Priority': '4'},
    timeout=10)
print(f'Notificación enviada: {r.status_code}')
"

# Lanzar revalidación en tmux
tmux new-session -d -s revalidate "bash -lc 'cd $REPO_ROOT && set -a && source .env && set +a && uv run python scripts/revalidate_all.py --wait 300 2>&1 | tee results/revalidate-\$(date -u +%Y%m%dT%H%M%SZ).log; echo EXIT:\$?'"

echo "✓ Revalidación iniciada en tmux session 'revalidate'"
