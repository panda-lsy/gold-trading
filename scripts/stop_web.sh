#!/bin/bash
# 停止Web服务器

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ -f ".portal_pid" ]; then
    PID=$(cat .portal_pid)
    kill "$PID" 2>/dev/null && echo "✓ Web服务器已停止" || echo "Web服务器未运行"
    rm -f .portal_pid
else
    pkill -f "http.server 8090" && echo "✓ Web服务器已停止" || echo "Web服务器未运行"
fi
