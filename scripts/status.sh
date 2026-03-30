#!/bin/bash
# 查看积存金交易系统状态

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f .service_ports.env ]; then
    # shellcheck disable=SC1091
    source .service_ports.env
fi

WS_PORT="${WS_PORT:-8765}"
DASHBOARD_PORT="${DASHBOARD_PORT:-5000}"
API_PORT="${API_PORT:-8080}"
PORTAL_PORT="${PORTAL_PORT:-8090}"

if command -v ss >/dev/null 2>&1; then
    PORT_CHECK_CMD="ss -tlnp"
elif command -v netstat >/dev/null 2>&1; then
    PORT_CHECK_CMD="netstat -tlnp"
else
    PORT_CHECK_CMD=""
fi

echo "=========================================="
echo "积存金交易系统状态"
echo "=========================================="
echo ""

# WebSocket 状态
echo "[1] WebSocket 服务 ($WS_PORT):"
if [ -f .ws_pid ] && ps -p $(cat .ws_pid) > /dev/null 2>&1; then
    echo "  ✓ 运行中 (PID: $(cat .ws_pid))"
    if [ -n "$PORT_CHECK_CMD" ]; then
        eval "$PORT_CHECK_CMD" 2>/dev/null | grep "$WS_PORT" | head -1
    fi
else
    echo "  ✗ 未运行"
fi
echo ""

# Dashboard 状态
echo "[2] Dashboard Web ($DASHBOARD_PORT):"
if [ -f .web_pid ] && ps -p $(cat .web_pid) > /dev/null 2>&1; then
    echo "  ✓ 运行中 (PID: $(cat .web_pid))"
    if [ -n "$PORT_CHECK_CMD" ]; then
        eval "$PORT_CHECK_CMD" 2>/dev/null | grep "$DASHBOARD_PORT" | head -1
    fi
else
    echo "  ✗ 未运行"
fi
echo ""

# API 服务器状态
echo "[3] API 服务器 ($API_PORT):"
if [ -f .api_pid ] && ps -p $(cat .api_pid) > /dev/null 2>&1; then
    echo "  ✓ 运行中 (PID: $(cat .api_pid))"
    if [ -n "$PORT_CHECK_CMD" ]; then
        eval "$PORT_CHECK_CMD" 2>/dev/null | grep "$API_PORT" | head -1
    fi
else
    echo "  ✗ 未运行"
fi
echo ""

# 静态 Portal 状态
echo "[4] Static Portal ($PORTAL_PORT):"
if [ -f .portal_pid ] && ps -p $(cat .portal_pid) > /dev/null 2>&1; then
    echo "  ✓ 运行中 (PID: $(cat .portal_pid))"
    if [ -n "$PORT_CHECK_CMD" ]; then
        eval "$PORT_CHECK_CMD" 2>/dev/null | grep "$PORTAL_PORT" | head -1
    fi
else
    echo "  ✗ 未运行"
fi
echo ""

# 访问地址
echo "=========================================="
echo "访问地址:"
echo "=========================================="
echo "  Dashboard:    http://127.0.0.1:$DASHBOARD_PORT"
echo "  WebSocket:    ws://127.0.0.1:$WS_PORT"
echo "  API Server:   http://127.0.0.1:$API_PORT"
echo "  Portal:       http://127.0.0.1:$PORTAL_PORT"
echo ""
echo "API 测试:"
echo "  curl http://127.0.0.1:$API_PORT/api/health"
echo "  curl http://127.0.0.1:$API_PORT/api/prices"
echo "  curl http://127.0.0.1:$API_PORT/api/dashboard"
echo ""

# 最近日志
echo "=========================================="
echo "最近日志:"
echo "=========================================="

for service in websocket dashboard api web; do
    echo ""
    echo "[$service]:"
    if [ -f logs/${service}.log ]; then
        tail -3 logs/${service}.log 2>/dev/null | sed 's/^/  /'
    else
        echo "  (无日志)"
    fi
done

echo ""
echo "=========================================="
