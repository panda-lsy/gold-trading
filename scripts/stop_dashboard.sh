#!/bin/bash
# 停止积存金 Dashboard 和 WebSocket 服务

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "停止服务..."

# 停止 Dashboard
if [ -f .web_pid ]; then
    kill "$(cat .web_pid)" 2>/dev/null || true
    rm .web_pid
    echo "✓ Dashboard 已停止"
fi

# 停止 WebSocket
if [ -f .ws_pid ]; then
    kill "$(cat .ws_pid)" 2>/dev/null || true
    rm .ws_pid
    echo "✓ WebSocket 已停止"
fi

# 清理进程
pkill -f "dashboard.py" 2>/dev/null || true
pkill -f "dashboard_v2.py" 2>/dev/null || true
pkill -f "dashboard_v3.py" 2>/dev/null || true
pkill -f "websocket_server.py" 2>/dev/null || true

echo "✓ 所有服务已停止"
