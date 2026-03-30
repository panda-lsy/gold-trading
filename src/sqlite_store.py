#!/usr/bin/env python3
"""
SQLite 持久化存储层。
包含交易状态、K线历史、预警规则与预警历史，支持版本化 schema 迁移。
"""
import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Dict, List, Optional


class SQLiteStore:
    """轻量 SQLite 存储，提供统一的读写接口。"""

    SCHEMA_LATEST_VERSION = 2

    def __init__(self, data_dir: str = None, db_path: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        os.makedirs(data_dir, exist_ok=True)

        env_path = os.getenv('SQLITE_DB_PATH')
        self.db_path = db_path or env_path or os.path.join(data_dir, 'gold_trading.db')
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _normalize_journal_mode(self):
        mode = (os.getenv('SQLITE_JOURNAL_MODE', 'WAL') or 'WAL').strip().upper()
        allowed = {'DELETE', 'TRUNCATE', 'PERSIST', 'MEMORY', 'WAL', 'OFF'}
        return mode if mode in allowed else 'WAL'

    def _init_db(self):
        with self._lock:
            with self._connect() as conn:
                journal_mode = self._normalize_journal_mode()
                conn.execute(f'PRAGMA journal_mode={journal_mode}')
                conn.execute('PRAGMA synchronous=NORMAL')
                conn.execute('PRAGMA foreign_keys=ON')
                self._apply_migrations(conn)

    def _apply_migrations(self, conn):
        current_version = int(conn.execute('PRAGMA user_version').fetchone()[0])
        migrations = {
            1: self._migration_v1,
            2: self._migration_v2,
        }

        for version in sorted(migrations.keys()):
            if current_version >= version:
                continue
            migrations[version](conn)
            conn.execute(f'PRAGMA user_version={version}')
            self._record_migration(conn, version)
            current_version = version

    def _record_migration(self, conn, version: int):
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            'INSERT OR REPLACE INTO schema_migrations(version, applied_at) VALUES (?, ?)',
            (version, datetime.now().isoformat()),
        )

    def _migration_v1(self, conn):
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trader_state (
                bank TEXT PRIMARY KEY,
                balance REAL NOT NULL,
                position REAL NOT NULL,
                avg_price REAL NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trader_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank TEXT NOT NULL,
                trade_index INTEGER NOT NULL,
                trade_json TEXT NOT NULL,
                UNIQUE(bank, trade_index)
            );

            CREATE INDEX IF NOT EXISTS idx_trader_trades_bank_index
            ON trader_trades(bank, trade_index);

            CREATE TABLE IF NOT EXISTS kline_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                datetime TEXT,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                UNIQUE(bank, timestamp)
            );

            CREATE INDEX IF NOT EXISTS idx_kline_bank_ts
            ON kline_history(bank, timestamp);
            """
        )

    def _migration_v2(self, conn):
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS alert_rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                bank TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                threshold REAL NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                triggered_at TEXT,
                triggered_count INTEGER NOT NULL DEFAULT 0,
                cooldown_minutes INTEGER NOT NULL DEFAULT 60,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_alert_rules_bank_enabled
            ON alert_rules(bank, enabled);

            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                rule_id TEXT,
                rule_name TEXT,
                bank TEXT,
                alert_type TEXT,
                message TEXT,
                current_value REAL,
                threshold REAL
            );

            CREATE INDEX IF NOT EXISTS idx_alert_history_bank_ts
            ON alert_history(bank, timestamp DESC);
            """
        )

    def get_schema_version(self):
        with self._lock:
            with self._connect() as conn:
                return int(conn.execute('PRAGMA user_version').fetchone()[0])

    def get_migration_history(self):
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT version, applied_at
                    FROM schema_migrations
                    ORDER BY version ASC
                    """
                ).fetchall()
        return [dict(row) for row in rows]

    def save_trader_state(self, bank: str, state: Dict):
        trades = state.get('trades', []) if isinstance(state, dict) else []
        timestamp = state.get('timestamp', '') if isinstance(state, dict) else ''

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO trader_state(bank, balance, position, avg_price, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(bank) DO UPDATE SET
                        balance=excluded.balance,
                        position=excluded.position,
                        avg_price=excluded.avg_price,
                        updated_at=excluded.updated_at
                    """,
                    (
                        bank,
                        float(state.get('balance', 0)),
                        float(state.get('position', 0)),
                        float(state.get('avg_price', 0)),
                        str(timestamp),
                    ),
                )
                conn.execute('DELETE FROM trader_trades WHERE bank = ?', (bank,))
                if trades:
                    conn.executemany(
                        'INSERT INTO trader_trades(bank, trade_index, trade_json) VALUES (?, ?, ?)',
                        [
                            (bank, i, json.dumps(trade, ensure_ascii=False))
                            for i, trade in enumerate(trades)
                        ],
                    )

    def load_trader_state(self, bank: str) -> Optional[Dict]:
        with self._lock:
            with self._connect() as conn:
                state_row = conn.execute(
                    'SELECT bank, balance, position, avg_price, updated_at FROM trader_state WHERE bank = ?',
                    (bank,),
                ).fetchone()
                if state_row is None:
                    return None

                trade_rows = conn.execute(
                    'SELECT trade_json FROM trader_trades WHERE bank = ? ORDER BY trade_index ASC',
                    (bank,),
                ).fetchall()

        trades: List[Dict] = []
        for row in trade_rows:
            try:
                parsed = json.loads(row['trade_json'])
                if isinstance(parsed, dict):
                    trades.append(parsed)
            except Exception:
                continue

        return {
            'bank': state_row['bank'],
            'balance': float(state_row['balance']),
            'position': float(state_row['position']),
            'avg_price': float(state_row['avg_price']),
            'trades': trades,
            'timestamp': state_row['updated_at'],
        }

    def load_trader_trades(self, bank: str = None) -> List[Dict]:
        if bank:
            query = 'SELECT bank, trade_json FROM trader_trades WHERE bank = ? ORDER BY trade_index ASC'
            params = (bank,)
        else:
            query = 'SELECT bank, trade_json FROM trader_trades ORDER BY bank ASC, trade_index ASC'
            params = ()

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(query, params).fetchall()

        trades: List[Dict] = []
        for row in rows:
            try:
                parsed = json.loads(row['trade_json'])
                if isinstance(parsed, dict):
                    parsed.setdefault('bank', row['bank'])
                    trades.append(parsed)
            except Exception:
                continue
        return trades

    def append_kline(self, bank: str, item: Dict):
        if not isinstance(item, dict) or 'timestamp' not in item:
            return

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO kline_history(bank, timestamp, datetime, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(bank, timestamp) DO UPDATE SET
                        datetime=excluded.datetime,
                        open=excluded.open,
                        high=excluded.high,
                        low=excluded.low,
                        close=excluded.close,
                        volume=excluded.volume
                    """,
                    (
                        bank,
                        int(item.get('timestamp', 0)),
                        item.get('datetime', ''),
                        float(item.get('open', 0)),
                        float(item.get('high', 0)),
                        float(item.get('low', 0)),
                        float(item.get('close', 0)),
                        float(item.get('volume', 0)),
                    ),
                )
                conn.execute(
                    """
                    DELETE FROM kline_history
                    WHERE id IN (
                        SELECT id FROM kline_history
                        WHERE bank = ?
                        ORDER BY timestamp DESC
                        LIMIT -1 OFFSET 10000
                    )
                    """,
                    (bank,),
                )

    def replace_kline_history(self, bank: str, items: List[Dict]):
        dedup = {}
        for item in items or []:
            if not isinstance(item, dict) or 'timestamp' not in item:
                continue
            ts = int(item.get('timestamp', 0))
            dedup[ts] = {
                'timestamp': ts,
                'datetime': item.get('datetime', ''),
                'open': float(item.get('open', 0)),
                'high': float(item.get('high', 0)),
                'low': float(item.get('low', 0)),
                'close': float(item.get('close', 0)),
                'volume': float(item.get('volume', 0)),
            }

        ordered = [dedup[ts] for ts in sorted(dedup.keys())]
        normalized = ordered[-10000:]
        with self._lock:
            with self._connect() as conn:
                conn.execute('DELETE FROM kline_history WHERE bank = ?', (bank,))
                if normalized:
                    conn.executemany(
                        """
                        INSERT INTO kline_history(bank, timestamp, datetime, open, high, low, close, volume)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                bank,
                                item['timestamp'],
                                item.get('datetime', ''),
                                item['open'],
                                item['high'],
                                item['low'],
                                item['close'],
                                item['volume'],
                            )
                            for item in normalized
                        ],
                    )

    def load_kline_history(self, bank: str, limit: int = 10000) -> List[Dict]:
        cap = max(1, min(int(limit or 10000), 10000))
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT timestamp, datetime, open, high, low, close, volume
                    FROM (
                        SELECT timestamp, datetime, open, high, low, close, volume
                        FROM kline_history
                        WHERE bank = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ) recent
                    ORDER BY timestamp ASC
                    """,
                    (bank, cap),
                ).fetchall()

        return [
            {
                'timestamp': int(row['timestamp']),
                'datetime': row['datetime'],
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']),
            }
            for row in rows
        ]

    def save_alert_rules(self, rules: List[Dict]):
        now = datetime.now().isoformat()
        normalized = []
        for rule in rules or []:
            if not isinstance(rule, dict) or not rule.get('id'):
                continue
            normalized.append(
                (
                    str(rule.get('id')),
                    str(rule.get('name', '')),
                    str(rule.get('bank', '')),
                    str(rule.get('alert_type', '')),
                    float(rule.get('threshold', 0)),
                    1 if bool(rule.get('enabled', True)) else 0,
                    str(rule.get('created_at') or now),
                    str(rule.get('triggered_at')) if rule.get('triggered_at') else None,
                    int(rule.get('triggered_count', 0)),
                    int(rule.get('cooldown_minutes', 60)),
                    now,
                )
            )

        with self._lock:
            with self._connect() as conn:
                conn.execute('DELETE FROM alert_rules')
                if normalized:
                    conn.executemany(
                        """
                        INSERT INTO alert_rules(
                            id, name, bank, alert_type, threshold, enabled,
                            created_at, triggered_at, triggered_count, cooldown_minutes, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        normalized,
                    )

    def load_alert_rules(self, bank: str = None, enabled_only: bool = False) -> List[Dict]:
        conditions = []
        params = []
        if bank:
            conditions.append('bank = ?')
            params.append(bank)
        if enabled_only:
            conditions.append('enabled = 1')

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ''
        query = (
            'SELECT id, name, bank, alert_type, threshold, enabled, created_at, triggered_at, '
            'triggered_count, cooldown_minutes FROM alert_rules '
            f'{where_clause} ORDER BY created_at DESC'
        )

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(query, tuple(params)).fetchall()

        return [
            {
                'id': row['id'],
                'name': row['name'],
                'bank': row['bank'],
                'alert_type': row['alert_type'],
                'threshold': float(row['threshold']),
                'enabled': bool(row['enabled']),
                'created_at': row['created_at'],
                'triggered_at': row['triggered_at'],
                'triggered_count': int(row['triggered_count']),
                'cooldown_minutes': int(row['cooldown_minutes']),
            }
            for row in rows
        ]

    def save_alert_history(self, history: List[Dict]):
        with self._lock:
            with self._connect() as conn:
                conn.execute('DELETE FROM alert_history')
                self.append_alert_history(history, connection=conn)

    def append_alert_history(self, entries: List[Dict], connection=None):
        normalized = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            normalized.append(
                (
                    str(entry.get('timestamp') or datetime.now().isoformat()),
                    str(entry.get('rule_id')) if entry.get('rule_id') is not None else None,
                    str(entry.get('rule_name')) if entry.get('rule_name') is not None else None,
                    str(entry.get('bank')) if entry.get('bank') is not None else None,
                    str(entry.get('alert_type')) if entry.get('alert_type') is not None else None,
                    str(entry.get('message')) if entry.get('message') is not None else None,
                    float(entry.get('current_value', 0)) if entry.get('current_value') is not None else None,
                    float(entry.get('threshold', 0)) if entry.get('threshold') is not None else None,
                )
            )

        if connection is not None:
            conn = connection
            owns_connection = False
        else:
            conn = self._connect()
            owns_connection = True

        try:
            if normalized:
                conn.executemany(
                    """
                    INSERT INTO alert_history(
                        timestamp, rule_id, rule_name, bank, alert_type, message, current_value, threshold
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    normalized,
                )
                conn.execute(
                    """
                    DELETE FROM alert_history
                    WHERE id IN (
                        SELECT id FROM alert_history
                        ORDER BY timestamp DESC
                        LIMIT -1 OFFSET 5000
                    )
                    """
                )
            if owns_connection:
                conn.commit()
        finally:
            if owns_connection:
                conn.close()

    def load_alert_history(self, bank: str = None, limit: int = 50) -> List[Dict]:
        cap = max(1, min(int(limit or 50), 5000))
        if bank:
            query = (
                'SELECT timestamp, rule_id, rule_name, bank, alert_type, message, current_value, threshold '
                'FROM alert_history WHERE bank = ? ORDER BY timestamp DESC LIMIT ?'
            )
            params = (bank, cap)
        else:
            query = (
                'SELECT timestamp, rule_id, rule_name, bank, alert_type, message, current_value, threshold '
                'FROM alert_history ORDER BY timestamp DESC LIMIT ?'
            )
            params = (cap,)

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(query, params).fetchall()

        return [
            {
                'timestamp': row['timestamp'],
                'rule_id': row['rule_id'],
                'rule_name': row['rule_name'],
                'bank': row['bank'],
                'alert_type': row['alert_type'],
                'message': row['message'],
                'current_value': row['current_value'],
                'threshold': row['threshold'],
            }
            for row in rows
        ]

    def clear_alert_history(self):
        with self._lock:
            with self._connect() as conn:
                conn.execute('DELETE FROM alert_history')
