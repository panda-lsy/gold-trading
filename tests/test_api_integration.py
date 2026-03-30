import os
import unittest
from unittest import mock

from app.api_server import APIServer


class APIServerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._old_recorder_flag = os.environ.get('ENABLE_INTERNAL_KLINE_RECORDER')
        os.environ['ENABLE_INTERNAL_KLINE_RECORDER'] = '0'

    @classmethod
    def tearDownClass(cls):
        if cls._old_recorder_flag is None:
            os.environ.pop('ENABLE_INTERNAL_KLINE_RECORDER', None)
        else:
            os.environ['ENABLE_INTERNAL_KLINE_RECORDER'] = cls._old_recorder_flag

    def setUp(self):
        proxy_patch = mock.patch('app.api_server.find_working_proxy', return_value=None)
        self.addCleanup(proxy_patch.stop)
        proxy_patch.start()

        self.server = APIServer()
        self.client = self.server.app.test_client()

        self.server.kline_service.get_kline_data = mock.Mock(return_value=[
            {
                'time': 1710000000000,
                'datetime': '2026-03-30 10:00:00',
                'open': 100.0,
                'high': 101.0,
                'low': 99.8,
                'close': 100.6,
                'volume': 12.3,
            }
        ])
        self.server.kline_service.record_price = mock.Mock(return_value=True)

        self.server.ai_bridge.get_capabilities = mock.Mock(return_value={
            'asr': {'ready': True, 'message': 'ready'},
            'tts': {'ready': True, 'message': 'ready'},
            'vlm': {'ready': True, 'message': 'ready'},
            'image_generation': {'ready': True, 'message': 'ready'},
        })

    def test_health_endpoint(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload['status'], 'ok')
        self.assertIn('timestamp', payload)

    def test_kline_endpoint(self):
        response = self.client.get('/api/kline/zheshang?period=1m&limit=5')
        self.assertEqual(response.status_code, 200)

        payload = response.get_json()
        self.assertEqual(payload['bank'], 'zheshang')
        self.assertEqual(payload['period'], '1m')
        self.assertEqual(payload['count'], 1)
        self.assertEqual(len(payload['data']), 1)

        self.server.kline_service.get_kline_data.assert_called_with('zheshang', '1m', 5)

    def test_ai_capabilities_endpoint(self):
        response = self.client.get('/api/ai/capabilities')
        self.assertEqual(response.status_code, 200)

        payload = response.get_json()
        self.assertTrue(payload['success'])
        self.assertIn('capabilities', payload)
        self.assertTrue(payload['capabilities']['vlm']['ready'])

    def test_error_response_is_normalized(self):
        response = self.client.get('/api/kline/invalid-bank')
        self.assertEqual(response.status_code, 400)

        payload = response.get_json()
        self.assertFalse(payload['success'])
        self.assertEqual(payload['code'], 'BAD_REQUEST')
        self.assertIn('message', payload)
        self.assertIn('request_id', payload)
        self.assertEqual(response.headers.get('X-Request-ID'), payload['request_id'])

    def test_rate_limit_block_returns_standard_error(self):
        self.server.rate_limit_ip_whitelist = set()
        self.server._resolve_rate_limit_per_minute = lambda _path: (2, 'test')

        self.assertEqual(self.client.get('/api/ai/capabilities').status_code, 200)
        self.assertEqual(self.client.get('/api/ai/capabilities').status_code, 200)

        blocked = self.client.get('/api/ai/capabilities')
        self.assertEqual(blocked.status_code, 429)
        payload = blocked.get_json()
        self.assertEqual(payload['code'], 'RATE_LIMIT_EXCEEDED')
        self.assertIn('details', payload)
        self.assertIn('retry_after_seconds', payload['details'])


if __name__ == '__main__':
    unittest.main()
