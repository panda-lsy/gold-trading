#!/bin/bash
# 启动Web服务器

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$PROJECT_ROOT/web"
LOG_DIR="$PROJECT_ROOT/logs"

mkdir -p "$WEB_DIR" "$LOG_DIR"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "错误: 未找到 Python 解释器 (python3/python)"
    exit 1
fi

cd "$WEB_DIR"

echo "启动Web服务器..."
echo "访问地址: http://localhost:8090"
$PYTHON_CMD -m http.server 8090 > "$PROJECT_ROOT/logs/web.log" 2>&1 &
echo $! > "$PROJECT_ROOT/.portal_pid"
echo "✓ Web服务器已启动"
