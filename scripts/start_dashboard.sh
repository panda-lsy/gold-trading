#!/bin/bash
# 启动积存金 Dashboard 和 WebSocket 服务

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

mkdir -p logs

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

load_existing_ports() {
    if [ -f .service_ports.env ]; then
        # shellcheck disable=SC1091
        source .service_ports.env
    fi
}

save_service_ports() {
    cat > .service_ports.env <<EOF
WS_PORT=$WS_PORT
DASHBOARD_PORT=$DASHBOARD_PORT
API_PORT=$API_PORT
PORTAL_PORT=$PORTAL_PORT
EOF
}

write_runtime_config() {
    local api_base="${PUBLIC_API_BASE:-${NATAPP_API_BASE:-http://127.0.0.1:$API_PORT}}"
    local dashboard_base="${PUBLIC_DASHBOARD_BASE:-${NATAPP_DASHBOARD_BASE:-http://127.0.0.1:$DASHBOARD_PORT}}"
    cat > web/runtime-config.js <<EOF
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

if command -v pip3 >/dev/null 2>&1; then
    PIP_CMD="pip3"
elif command -v pip >/dev/null 2>&1; then
    PIP_CMD="pip"
else
    PIP_CMD=""
fi

echo "=========================================="
echo "积存金交易 Dashboard 启动脚本"
echo "=========================================="

# 检查 Flask 依赖
echo "检查依赖..."
${PYTHON_CMD} -c "import flask" 2>/dev/null || {
    echo "安装 Flask..."
    if [ -n "$PIP_CMD" ]; then
        $PIP_CMD install flask flask-cors websockets -q
    else
        echo "错误: 未找到 pip，无法自动安装依赖"
        exit 1
    fi
}

# 停止旧进程
echo "停止旧进程..."
pkill -f "dashboard.py" 2>/dev/null || true
pkill -f "dashboard_v2.py" 2>/dev/null || true
pkill -f "dashboard_v3.py" 2>/dev/null || true
pkill -f "websocket_server.py" 2>/dev/null || true
sleep 1

load_existing_ports
WS_PORT="${WS_PORT:-8765}"
DASHBOARD_PORT="${DASHBOARD_PORT:-5000}"
API_PORT="${API_PORT:-8080}"
PORTAL_PORT="${PORTAL_PORT:-8090}"

WS_PORT="$(find_available_port "$WS_PORT" 8700 8999)"
DASHBOARD_PORT="$(find_available_port "$DASHBOARD_PORT" 5000 5999)"

save_service_ports
write_runtime_config

# 启动 WebSocket 服务
echo "启动 WebSocket 服务..."
nohup $PYTHON_CMD src/websocket_server.py --host 0.0.0.0 --port "$WS_PORT" > logs/websocket.log 2>&1 &
WS_PID=$!
echo "WebSocket PID: $WS_PID"
echo $WS_PID > .ws_pid

# 等待 WebSocket 启动
sleep 2

# 启动 Dashboard
echo "启动 Dashboard Web 服务..."
if [ -f app/dashboard_v3.py ]; then
    nohup $PYTHON_CMD app/dashboard_v3.py --host 0.0.0.0 --port "$DASHBOARD_PORT" > logs/dashboard.log 2>&1 &
else
    echo "错误: 找不到 app/dashboard_v3.py"
    exit 1
fi
WEB_PID=$!
echo "Dashboard PID: $WEB_PID"
echo $WEB_PID > .web_pid

sleep 2

echo ""
echo "=========================================="
echo "✓ 服务启动完成"
echo "=========================================="
echo "Dashboard: http://127.0.0.1:$DASHBOARD_PORT"
echo "WebSocket: ws://127.0.0.1:$WS_PORT"
echo ""
echo "日志:"
echo "  WebSocket: logs/websocket.log"
echo "  Dashboard: logs/dashboard.log"
echo ""
echo "停止服务：./scripts/stop_dashboard.sh"
echo "查看状态：./scripts/status.sh"
echo "=========================================="
