#!/usr/bin/env python3
"""
设置 OpenClaw 定时任务模板
仅支持生产版配置
"""
import json
import argparse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_FILES = {
    'production': PROJECT_ROOT / 'config' / 'openclaw_cron.production.json',
}
TARGET_FILE = PROJECT_ROOT / 'openclaw_cron.json'


def load_template(mode: str):
    template_file = TEMPLATE_FILES[mode]
    if not template_file.exists():
        raise FileNotFoundError(f'模板不存在: {template_file}')

    with open(template_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def apply_template(mode: str):
    payload = load_template(mode)
    with open(TARGET_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'✓ 已应用 {mode} 模板到 {TARGET_FILE}')

def setup_instructions(mode: str):
    """设置说明"""
    print(f"积存金 OpenClaw 定时任务设置 ({mode})")
    print("=" * 60)
    print(f"模板文件: {TEMPLATE_FILES[mode]}")
    print(f"目标文件: {TARGET_FILE}")
    print()

    payload = load_template(mode)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='OpenClaw 定时任务模板工具')
    parser.add_argument('--mode', choices=['production'], default='production')
    parser.add_argument('--apply', action='store_true', help='将模板写入 openclaw_cron.json')
    args = parser.parse_args()

    setup_instructions(args.mode)
    if args.apply:
        apply_template(args.mode)
    
    print()
    print("=" * 60)
    print("文件结构:")
    print("=" * 60)
    
    files = [
        ("app/dashboard_v3.py", "Dashboard 主面板"),
        ("app/openclaw_integration.py", "OpenClaw集成模块"),
        ("ops/jijin_service.py", "积存金服务 - 定时任务"),
        ("openclaw_cron.json", "当前生效的 OpenClaw 配置"),
        ("config/openclaw_cron.production.json", "生产版模板"),
        ("src/jijin_trader.py", "积存金交易核心"),
        ("src/jijin_strategy.py", "积存金策略"),
    ]
    
    for file, desc in files:
        path = PROJECT_ROOT / file
        exists = "✓" if path.exists() else "✗"
        print(f"{exists} {file:<30} {desc}")
