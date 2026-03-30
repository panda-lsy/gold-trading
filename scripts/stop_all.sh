#!/bin/bash
# 停止积存金交易系统所有服务

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "停止所有服务..."

# 停止 API 服务器
if [ -f .api_pid ]; then
    kill "$(cat .api_pid)" 2>/dev/null || true
    rm .api_pid
    echo "✓ API 服务器已停止"
fi

# 停止 Dashboard
if [ -f .web_pid ]; then
    kill "$(cat .web_pid)" 2>/dev/null || true
    rm .web_pid
    echo "✓ Dashboard 已停止"
fi
pkill -f "dashboard.py" 2>/dev/null || true
pkill -f "dashboard_v2.py" 2>/dev/null || true
pkill -f "dashboard_v3.py" 2>/dev/null || true

# 停止 WebSocket
if [ -f .ws_pid ]; then
    kill "$(cat .ws_pid)" 2>/dev/null || true
    rm .ws_pid
    echo "✓ WebSocket 已停止"
fi

# 停止静态 Portal
if [ -f .portal_pid ]; then
    kill "$(cat .portal_pid)" 2>/dev/null || true
    rm .portal_pid
    echo "✓ Web Portal 已停止"
fi

# 清理残留进程
pkill -f "api_server.py" 2>/dev/null || true
pkill -f "websocket_server.py" 2>/dev/null || true
pkill -f "http.server 8090" 2>/dev/null || true

echo "✓ 所有服务已停止"
