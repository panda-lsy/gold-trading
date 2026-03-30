#!/bin/bash
# 查看积存金交易系统状态

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

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
echo "[1] WebSocket 服务 (8765):"
if [ -f .ws_pid ] && ps -p $(cat .ws_pid) > /dev/null 2>&1; then
    echo "  ✓ 运行中 (PID: $(cat .ws_pid))"
    if [ -n "$PORT_CHECK_CMD" ]; then
        eval "$PORT_CHECK_CMD" 2>/dev/null | grep 8765 | head -1
    fi
else
    echo "  ✗ 未运行"
fi
echo ""

# Dashboard 状态
echo "[2] Dashboard Web (5000):"
if [ -f .web_pid ] && ps -p $(cat .web_pid) > /dev/null 2>&1; then
    echo "  ✓ 运行中 (PID: $(cat .web_pid))"
    if [ -n "$PORT_CHECK_CMD" ]; then
        eval "$PORT_CHECK_CMD" 2>/dev/null | grep 5000 | head -1
    fi
else
    echo "  ✗ 未运行"
fi
echo ""

# API 服务器状态
echo "[3] API 服务器 (8080):"
if [ -f .api_pid ] && ps -p $(cat .api_pid) > /dev/null 2>&1; then
    echo "  ✓ 运行中 (PID: $(cat .api_pid))"
    if [ -n "$PORT_CHECK_CMD" ]; then
        eval "$PORT_CHECK_CMD" 2>/dev/null | grep 8080 | head -1
    fi
else
    echo "  ✗ 未运行"
fi
echo ""

# 静态 Portal 状态
echo "[4] Static Portal (8090):"
if [ -f .portal_pid ] && ps -p $(cat .portal_pid) > /dev/null 2>&1; then
    echo "  ✓ 运行中 (PID: $(cat .portal_pid))"
    if [ -n "$PORT_CHECK_CMD" ]; then
        eval "$PORT_CHECK_CMD" 2>/dev/null | grep 8090 | head -1
    fi
else
    echo "  ✗ 未运行"
fi
echo ""

# 访问地址
echo "=========================================="
echo "访问地址:"
echo "=========================================="
echo "  Dashboard:    http://127.0.0.1:5000"
echo "  WebSocket:    ws://127.0.0.1:8765"
echo "  API Server:   http://127.0.0.1:8080"
echo "  Portal:       http://127.0.0.1:8090"
echo ""
echo "API 测试:"
echo "  curl http://127.0.0.1:8080/api/health"
echo "  curl http://127.0.0.1:8080/api/prices"
echo "  curl http://127.0.0.1:8080/api/dashboard"
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
