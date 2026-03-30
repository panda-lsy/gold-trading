import tempfile
import unittest
import os
import gc

from src.sqlite_store import SQLiteStore


class SQLiteStoreTests(unittest.TestCase):
    def setUp(self):
        self._old_journal_mode = os.environ.get('SQLITE_JOURNAL_MODE')
        os.environ['SQLITE_JOURNAL_MODE'] = 'DELETE'
        self._tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(data_dir=self._tmp.name)

    def tearDown(self):
        self.store = None
        gc.collect()
        self._tmp.cleanup()
        if self._old_journal_mode is None:
            os.environ.pop('SQLITE_JOURNAL_MODE', None)
        else:
            os.environ['SQLITE_JOURNAL_MODE'] = self._old_journal_mode

    def test_trader_state_roundtrip(self):
        state = {
            'bank': 'zheshang',
            'balance': 12345.67,
            'position': 12.3,
            'avg_price': 555.5,
            'trades': [
                {'action': 'BUY', 'price': 500, 'grams': 1.2},
                {'action': 'SELL', 'price': 560, 'grams': 0.2, 'profit': 12.0},
            ],
            'timestamp': '2026-03-30T12:00:00',
        }
        self.store.save_trader_state('zheshang', state)

        loaded = self.store.load_trader_state('zheshang')
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['bank'], 'zheshang')
        self.assertAlmostEqual(loaded['balance'], state['balance'])
        self.assertAlmostEqual(loaded['position'], state['position'])
        self.assertEqual(len(loaded['trades']), 2)
        self.assertEqual(loaded['trades'][0]['action'], 'BUY')

    def test_kline_history_roundtrip_ordered(self):
        items = [
            {
                'timestamp': 1710000000000,
                'datetime': '2026-03-30 10:00:00',
                'open': 100.0,
                'high': 101.0,
                'low': 99.5,
                'close': 100.2,
                'volume': 10.0,
            },
            {
                'timestamp': 1710000060000,
                'datetime': '2026-03-30 10:01:00',
                'open': 100.2,
                'high': 101.2,
                'low': 100.1,
                'close': 100.8,
                'volume': 12.0,
            },
        ]
        self.store.replace_kline_history('zheshang', items)
        self.store.append_kline('zheshang', {
            'timestamp': 1710000120000,
            'datetime': '2026-03-30 10:02:00',
            'open': 100.8,
            'high': 101.5,
            'low': 100.6,
            'close': 101.1,
            'volume': 9.0,
        })

        loaded = self.store.load_kline_history('zheshang', limit=10)
        self.assertEqual(len(loaded), 3)
        self.assertLess(loaded[0]['timestamp'], loaded[-1]['timestamp'])
        self.assertEqual(loaded[-1]['close'], 101.1)


if __name__ == '__main__':
    unittest.main()
