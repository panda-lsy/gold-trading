#!/usr/bin/env python3
"""
SQLite 数据迁移脚本。

用途:
1. 初始化或升级 SQLite schema 到最新版本。
2. 将历史 JSON 数据迁移到 SQLite（交易状态、K线历史、预警规则与预警历史）。
"""
import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from json_store import load_json_file
from sqlite_store import SQLiteStore


def _load_json(path: Path, default):
    if not path.exists():
        return default
    data = load_json_file(str(path), default)
    return data


def migrate_trader_states(store: SQLiteStore, data_dir: Path, dry_run: bool):
    banks = ['zheshang', 'minsheng']
    migrated = 0
    migrated_trades = 0

    for bank in banks:
        state_path = data_dir / f'jijin_{bank}_state.json'
        state = _load_json(state_path, default={})
        if not isinstance(state, dict) or not state:
            continue

        if not dry_run:
            store.save_trader_state(bank, state)

        migrated += 1
        trades = state.get('trades', [])
        if isinstance(trades, list):
            migrated_trades += len(trades)

    return migrated, migrated_trades


def migrate_kline_history(store: SQLiteStore, data_dir: Path, dry_run: bool):
    banks = ['zheshang', 'minsheng']
    migrated = 0
    points = 0

    for bank in banks:
        kline_path = data_dir / f'{bank}_kline.json'
        history = _load_json(kline_path, default=[])
        if not isinstance(history, list) or not history:
            continue

        if not dry_run:
            store.replace_kline_history(bank, history)

        migrated += 1
        points += len(history)

    return migrated, points


def migrate_alerts(store: SQLiteStore, data_dir: Path, dry_run: bool):
    rules_path = data_dir / 'alert_rules.json'
    history_path = data_dir / 'alert_history.json'

    rules = _load_json(rules_path, default=[])
    history = _load_json(history_path, default=[])

    normalized_rules = rules if isinstance(rules, list) else []
    normalized_history = history if isinstance(history, list) else []

    if not dry_run:
        if normalized_rules:
            store.save_alert_rules(normalized_rules)
        if normalized_history:
            store.save_alert_history(normalized_history)

    return len(normalized_rules), len(normalized_history)


def main():
    parser = argparse.ArgumentParser(description='迁移 JSON 数据到 SQLite 并执行 schema 升级')
    parser.add_argument('--data-dir', default=str(PROJECT_ROOT / 'data'), help='数据目录路径')
    parser.add_argument('--dry-run', action='store_true', help='仅检查迁移规模，不写入 SQLite')
    parser.add_argument('--migrate-only', action='store_true', help='仅执行 schema 升级，不读取 JSON')
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    db_path = os.getenv('SQLITE_DB_PATH') or str(data_dir / 'gold_trading.db')
    print(f'[info] data_dir={data_dir}')
    print(f'[info] sqlite_db={db_path}')
    print(f'[info] dry_run={args.dry_run}')

    store = SQLiteStore(data_dir=str(data_dir), db_path=db_path)
    print(f'[info] schema_version={store.get_schema_version()}')

    history = store.get_migration_history()
    if history:
        print('[info] migration_history:')
        for item in history:
            print(f"  - v{item['version']} @ {item['applied_at']}")

    if args.migrate_only:
        print('[done] 仅 schema 升级完成。')
        return

    state_files, state_trades = migrate_trader_states(store, data_dir, args.dry_run)
    kline_files, kline_points = migrate_kline_history(store, data_dir, args.dry_run)
    rules_count, alert_history_count = migrate_alerts(store, data_dir, args.dry_run)

    print('[done] 迁移统计:')
    print(f'  - 交易状态文件: {state_files}')
    print(f'  - 交易记录条数: {state_trades}')
    print(f'  - K线文件: {kline_files}')
    print(f'  - K线点位数: {kline_points}')
    print(f'  - 预警规则数: {rules_count}')
    print(f'  - 预警历史数: {alert_history_count}')


if __name__ == '__main__':
    main()
