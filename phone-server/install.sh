#!/data/data/com.termux/files/usr/bin/bash
# phone-server — one-shot Termux bootstrap for a 24/7 Android AI server.
# Idempotent: safe to re-run. Requires Termux from F-Droid (not Play Store).
set -euo pipefail

ANDROIDLLM_DIR="${ANDROIDLLM_DIR:-$HOME/androidllm}"
BOT_DIR="$HOME/opencode-server-bot"
CYBERDECK_DIR="$HOME/cyberdeck"
SCRIPT_URL="${SCRIPT_URL:-https://raw.githubusercontent.com/bara36368-sketch/cyberdeck/main/phone-server}"

log()  { echo -e "\e[1;34m[phone-server]\e[0m $*"; }
warn() { echo -e "\e[1;33m[phone-server]\e[0m $*"; }
die()  { echo -e "\e[1;31m[phone-server]\e[0m $*" >&2; exit 1; }

command -v pkg >/dev/null || die "Termux package manager not found. Install Termux from F-Droid."

log "== Provisioning Android AI server on $(uname -m) =="

pkg update -y
pkg install -y python rust python-pip git \
  || warn "some packages failed; continuing (python+git are required)"

log "Installing python deps"
pip install -U pip

log "Cloning repos"
[ -d "$ANDROIDLLM_DIR" ] || git clone --depth 1 https://github.com/bara36368-sketch/androidllm.git "$ANDROIDLLM_DIR"
[ -d "$BOT_DIR" ]        || git clone --depth 1 https://github.com/bara36368-sketch/opencode-server-bot.git "$BOT_DIR"
[ -d "$CYBERDECK_DIR" ]  || git clone --depth 1 https://github.com/bara36368-sketch/cyberdeck.git "$CYBERDECK_DIR"

pip install -e "$ANDROIDLLM_DIR[dev]" || pip install -e "$ANDROIDLLM_DIR"

log "Installing supervisor scripts"
install -m 755 "$CYBERDECK_DIR/phone-server/run.sh"   "$PREFIX/bin/androidllm-run"
install -m 755 "$CYBERDECK_DIR/phone-server/monitor.sh" "$PREFIX/bin/androidllm-monitor"
install -m 755 "$CYBERDECK_DIR/phone-server/install.sh" "$PREFIX/bin/androidllm-install"

if [ ! -f "$ANDROIDLLM_DIR/api_key" ]; then
    log "No API key yet — will be auto-generated on first serve."
fi

log "Done. Start the server with:  androidllm-run"
log "Check health with:            curl http://127.0.0.1:8080/health"
