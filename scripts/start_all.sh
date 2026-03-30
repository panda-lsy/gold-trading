#!/bin/bash
# 启动积存金交易系统所有服务（WebSocket + Dashboard + API）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

mkdir -p logs

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
	$PIP_CMD install flask flask-cors websockets -q 2>/dev/null || true
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

# 1. 启动 WebSocket 服务
echo ""
echo "[1/3] 启动 WebSocket 服务..."
nohup $PYTHON_CMD src/websocket_server.py --host 0.0.0.0 --port 8765 > logs/websocket.log 2>&1 &
WS_PID=$!
echo $WS_PID > .ws_pid
echo "  ✓ WebSocket PID: $WS_PID"

sleep 2

# 2. 启动 Dashboard
echo ""
echo "[2/3] 启动 Dashboard Web 服务 (v3.0 - 专业K线)..."
if [ -f app/dashboard_v3.py ]; then
	nohup $PYTHON_CMD app/dashboard_v3.py --host 0.0.0.0 --port 5000 > logs/dashboard.log 2>&1 &
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
nohup $PYTHON_CMD app/api_server.py --host 0.0.0.0 --port 8080 > logs/api.log 2>&1 &
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
echo "  Dashboard (可视化): http://127.0.0.1:5000"
echo "  WebSocket (实时推送): ws://127.0.0.1:8765"
echo "  API Server (后端接口): http://127.0.0.1:8080"
echo ""
echo "API 端点示例:"
echo "  http://127.0.0.1:8080/api/prices       - 实时价格"
echo "  http://127.0.0.1:8080/api/trades       - 交易记录"
echo "  http://127.0.0.1:8080/api/kline/zheshang  - K线数据"
echo "  http://127.0.0.1:8080/api/dashboard    - 综合数据"
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
