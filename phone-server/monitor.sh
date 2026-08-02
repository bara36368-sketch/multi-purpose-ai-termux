#!/data/data/com.termux/files/usr/bin/bash
# monitor.sh — health checks + OOM downgrade ladder.
#
#   androidllm-monitor            # one health check; exits 1 when down
#   androidllm-monitor --watch    # loop: check every 30s, print status
#   androidllm-monitor --on-crash <rc>   # step down on OOM-class crash (rc 137/139)
set -uo pipefail

ANDROIDLLM_DIR="${ANDROIDLLM_DIR:-$HOME/androidllm}"
PORT="${PORT:-8080}"
CHECK_URL="http://127.0.0.1:$PORT/health"

is_up() {
    curl -fsS -m 5 "$CHECK_URL" >/dev/null 2>&1
}

step_down() {
    # Read current model, pick the next smaller one that is already sharded
    # (no download). Mirrors androidllm_models.next_smaller().
    python3 - "$ANDROIDLLM_DIR" "$1" <<'PY'
import json, os, sys
adir, rc = sys.argv[1], sys.argv[2]
LADDER = ["qwen3-32b", "qwen25-32b", "mistral-24b", "qwen3-14b", "qwen25-14b",
          "qwen3-8b", "qwen25-7b", "mistral-7b", "qwen3-4b", "qwen25-3b",
          "qwen3", "qwen15", "smollm2", "qwen3-06", "qwen05",
          "smollm2-360m", "smollm2-135m"]
try:
    cur = json.load(open(os.path.join(adir, "current_model.json"))).get("id")
except Exception:
    cur = None
if cur not in LADDER:
    print("current model not in ladder; leaving state untouched")
    sys.exit(0)
for mid in LADDER[LADDER.index(cur) + 1:]:
    if os.path.isfile(os.path.join(adir, "models", mid, "manifest.json")):
        with open(os.path.join(adir, "current_model.json"), "w") as f:
            json.dump({"id": mid, "path": os.path.join(adir, "models", mid)}, f)
        print(f"stepped down {cur} -> {mid} (OOM rc={rc})")
        sys.exit(0)
print(f"no smaller sharded model below {cur}; staying put")
PY
}

case "${1:-}" in
    --watch)
        while true; do
            if is_up; then
                echo "$(date -Is) ok"
            else
                echo "$(date -Is) DOWN"
            fi
            sleep 30
        done
        ;;
    --on-crash)
        rc="${2:-1}"
        case "$rc" in
            137|139)  # SIGKILL (OOM killer) / SIGSEGV
                echo "$(date -Is) OOM-class crash rc=$rc" >&2
                step_down "$rc"
                ;;
            *) echo "non-OOM rc=$rc; no ladder step" >&2 ;;
        esac
        ;;
    *)
        is_up
        ;;
esac
