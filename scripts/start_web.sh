#!/bin/bash
# 启动Web服务器

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$PROJECT_ROOT/web"
LOG_DIR="$PROJECT_ROOT/logs"

mkdir -p "$WEB_DIR" "$LOG_DIR"

load_existing_ports() {
    if [ -f "$PROJECT_ROOT/.service_ports.env" ]; then
        # shellcheck disable=SC1091
        source "$PROJECT_ROOT/.service_ports.env"
    fi
}

is_port_free() {
    local port="$1"
    $PYTHON_CMD - "$port" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("127.0.0.1", port))
    print("1")
except OSError:
    print("0")
finally:
    s.close()
PY
}

find_available_port() {
    local preferred="$1"
    local start="$2"
    local end="$3"

    if [ "$(is_port_free "$preferred")" = "1" ]; then
        echo "$preferred"
        return 0
    fi

    local p
    for ((p=start; p<=end; p++)); do
        if [ "$(is_port_free "$p")" = "1" ]; then
            echo "$p"
            return 0
        fi
    done

    echo "错误: 未找到可用端口 (${start}-${end})" >&2
    return 1
}

save_service_ports() {
    cat > "$PROJECT_ROOT/.service_ports.env" <<EOF
WS_PORT=$WS_PORT
DASHBOARD_PORT=$DASHBOARD_PORT
API_PORT=$API_PORT
PORTAL_PORT=$PORTAL_PORT
EOF
}

write_runtime_config() {
    local api_base="${PUBLIC_API_BASE:-${NATAPP_API_BASE:-http://127.0.0.1:$API_PORT}}"
    local dashboard_base="${PUBLIC_DASHBOARD_BASE:-${NATAPP_DASHBOARD_BASE:-http://127.0.0.1:$DASHBOARD_PORT}}"
    cat > "$PROJECT_ROOT/web/runtime-config.js" <<EOF
window.__API_BASE__ = '$api_base';
window.__DASHBOARD_BASE__ = '$dashboard_base';
EOF
}

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "错误: 未找到 Python 解释器 (python3/python)"
    exit 1
fi

load_existing_ports
WS_PORT="${WS_PORT:-8765}"
DASHBOARD_PORT="${DASHBOARD_PORT:-5000}"
API_PORT="${API_PORT:-8080}"
PORTAL_PORT="${PORTAL_PORT:-8090}"
PORTAL_PORT="$(find_available_port "$PORTAL_PORT" 8090 8999)"

save_service_ports
write_runtime_config

cd "$WEB_DIR"

echo "启动Web服务器..."
echo "访问地址: http://localhost:$PORTAL_PORT"
$PYTHON_CMD -m http.server "$PORTAL_PORT" > "$PROJECT_ROOT/logs/web.log" 2>&1 &
echo $! > "$PROJECT_ROOT/.portal_pid"
echo "✓ Web服务器已启动"
