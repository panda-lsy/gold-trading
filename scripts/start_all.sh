#!/bin/bash
# 启动积存金交易系统所有服务（WebSocket + Dashboard + API）

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
echo "积存金交易系统 - 启动所有服务"
echo "=========================================="

# 检查依赖
echo "检查依赖..."
if [ -n "$PIP_CMD" ]; then
	$PIP_CMD install flask flask-cors websockets aiohttp -q 2>/dev/null || true
else
	echo "  ! 未找到 pip，跳过依赖自动安装"
fi

# 停止旧进程
echo "停止旧进程..."
pkill -f "websocket_server.py" 2>/dev/null || true
pkill -f "dashboard.py" 2>/dev/null || true
pkill -f "dashboard_v2.py" 2>/dev/null || true
pkill -f "dashboard_v3.py" 2>/dev/null || true
pkill -f "api_server.py" 2>/dev/null || true
sleep 1

WS_PORT="${WS_PORT:-8765}"
DASHBOARD_PORT="${DASHBOARD_PORT:-5000}"
API_PORT="${API_PORT:-8080}"
PORTAL_PORT="${PORTAL_PORT:-8090}"

WS_PORT="$(find_available_port "$WS_PORT" 8700 8999)"
DASHBOARD_PORT="$(find_available_port "$DASHBOARD_PORT" 5000 5999)"
API_PORT="$(find_available_port "$API_PORT" 8000 8999)"
PORTAL_PORT="$(find_available_port "$PORTAL_PORT" 8090 8999)"

save_service_ports
write_runtime_config

# 1. 启动 WebSocket 服务
echo ""
echo "[1/3] 启动 WebSocket 服务..."
nohup $PYTHON_CMD src/websocket_server.py --host 0.0.0.0 --port "$WS_PORT" > logs/websocket.log 2>&1 &
WS_PID=$!
echo $WS_PID > .ws_pid
echo "  ✓ WebSocket PID: $WS_PID"

sleep 2

# 2. 启动 Dashboard
echo ""
echo "[2/3] 启动 Dashboard Web 服务 (v3.0 - 专业K线)..."
if [ -f app/dashboard_v3.py ]; then
	nohup $PYTHON_CMD app/dashboard_v3.py --host 0.0.0.0 --port "$DASHBOARD_PORT" > logs/dashboard.log 2>&1 &
else
	echo "错误: 找不到 app/dashboard_v3.py"
	exit 1
fi
DASH_PID=$!
echo $DASH_PID > .web_pid
echo "  ✓ Dashboard PID: $DASH_PID"

sleep 2

# 3. 启动 API 服务器
echo ""
echo "[3/3] 启动 API 服务器..."
nohup $PYTHON_CMD app/api_server.py --host 0.0.0.0 --port "$API_PORT" > logs/api.log 2>&1 &
API_PID=$!
echo $API_PID > .api_pid
echo "  ✓ API PID: $API_PID"

sleep 2

echo ""
echo "=========================================="
echo "✓ 所有服务启动完成"
echo "=========================================="
echo ""
echo "服务地址:"
echo "  Dashboard (可视化): http://127.0.0.1:$DASHBOARD_PORT"
echo "  WebSocket (实时推送): ws://127.0.0.1:$WS_PORT"
echo "  API Server (后端接口): http://127.0.0.1:$API_PORT"
echo ""
echo "API 端点示例:"
echo "  http://127.0.0.1:$API_PORT/api/prices       - 实时价格"
echo "  http://127.0.0.1:$API_PORT/api/trades       - 交易记录"
echo "  http://127.0.0.1:$API_PORT/api/kline/zheshang  - K线数据"
echo "  http://127.0.0.1:$API_PORT/api/dashboard    - 综合数据"
echo ""
echo "日志文件:"
echo "  logs/websocket.log  - WebSocket 日志"
echo "  logs/dashboard.log  - Dashboard 日志"
echo "  logs/api.log        - API 日志"
echo ""
echo "管理命令:"
echo "  ./scripts/stop_all.sh       - 停止所有服务"
echo "  ./scripts/status.sh         - 查看状态"
echo "=========================================="
