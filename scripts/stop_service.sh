#!/bin/bash
# 积存金服务停止脚本

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

PID_FILE=""
if [ -f ".service_pid" ]; then
    PID_FILE=".service_pid"
elif [ -f ".pid" ]; then
    PID_FILE=".pid"
fi

if [ -n "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" || true
        echo "✓ 服务已停止"
    else
        echo "服务未运行"
    fi
    rm -f .service_pid .pid
else
    pkill -f "jijin_service.py" && echo "✓ 服务已停止" || echo "服务未运行"
fi
