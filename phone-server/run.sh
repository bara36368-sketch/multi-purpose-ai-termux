#!/data/data/com.termux/files/usr/bin/bash
# run.sh — start androidllm-serve + bot under a watchdog loop.
# Restarts on crash with backoff; OOM-class crashes trigger the downgrade
# ladder via monitor.sh. Logs to ~/androidllm/logs/.
set -uo pipefail

ANDROIDLLM_DIR="${ANDROIDLLM_DIR:-$HOME/androidllm}"
LOG_DIR="$ANDROIDLLM_DIR/logs"
PORT="${PORT:-8080}"
MAX_BACKOFF="${MAX_BACKOFF:-60}"

mkdir -p "$LOG_DIR"

serve_cmd() {
    # If a current_model.json exists, serve that model; else the picker default.
    local model
    model=$(python3 -c "
import json, os
p = os.path.expanduser('$ANDROIDLLM_DIR/current_model.json')
try:
    print(json.load(open(p))['id'])
except Exception:
    print('')
")
    if [ -n "$model" ]; then
        echo "ANDROIDLLM_MODEL=$model python3 -m androidllm.serve --port $PORT"
    else
        echo "python3 -m androidllm.serve --port $PORT"
    fi
}

backoff=1
while true; do
    echo "$(date -Is) starting serve" >> "$LOG_DIR/run.log"
    cmd=$(serve_cmd)
    # shellcheck disable=SC2086
    if (cd "$ANDROIDLLM_DIR" && env $cmd >> "$LOG_DIR/serve.log" 2>&1); then
        backoff=1
    else
        rc=$?
        echo "$(date -Is) serve exited rc=$rc" >> "$LOG_DIR/run.log"
        "$PREFIX/bin/androidllm-monitor" --on-crash "$rc" >> "$LOG_DIR/monitor.log" 2>&1 || true
        sleep "$backoff"
        backoff=$(( backoff * 2 ))
        [ "$backoff" -gt "$MAX_BACKOFF" ] && backoff="$MAX_BACKOFF"
    fi
done
