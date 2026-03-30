#!/bin/bash
# 启动积存金 Dashboard 和 WebSocket 服务

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

# 启动 WebSocket 服务
echo "启动 WebSocket 服务..."
nohup $PYTHON_CMD src/websocket_server.py --host 0.0.0.0 --port 8765 > logs/websocket.log 2>&1 &
WS_PID=$!
echo "WebSocket PID: $WS_PID"
echo $WS_PID > .ws_pid

# 等待 WebSocket 启动
sleep 2

# 启动 Dashboard
echo "启动 Dashboard Web 服务..."
if [ -f app/dashboard_v3.py ]; then
    nohup $PYTHON_CMD app/dashboard_v3.py --host 0.0.0.0 --port 5000 > logs/dashboard.log 2>&1 &
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
echo "Dashboard: http://127.0.0.1:5000"
echo "WebSocket: ws://127.0.0.1:8765"
echo ""
echo "日志:"
echo "  WebSocket: logs/websocket.log"
echo "  Dashboard: logs/dashboard.log"
echo ""
echo "停止服务：./scripts/stop_dashboard.sh"
echo "查看状态：./scripts/status.sh"
echo "=========================================="
