#!/bin/bash
# 启动积存金监控服务（jijin_service.py）

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

# 检查是否已在运行
if pgrep -f "jijin_service.py" > /dev/null; then
    echo "服务已在运行"
    exit 0
fi

echo "启动积存金监控服务..."
nohup $PYTHON_CMD ops/jijin_service.py --mode service > logs/service.log 2>&1 &
echo $! > .service_pid
sleep 2

if pgrep -f "jijin_service.py" > /dev/null; then
    echo "✓ 服务已启动"
else
    echo "✗ 服务启动失败"
    exit 1
fi
