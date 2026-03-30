import unittest
from pathlib import Path

from flask import Flask

from app.api_server import APIServer, AI_OUTPUT_DIR


class APIServerValidationTests(unittest.TestCase):
    def setUp(self):
        self.server = object.__new__(APIServer)
        self.app = Flask(__name__)

    def test_resolve_artifact_path_allows_expected_file(self):
        target = self.server._resolve_artifact_path('sample.wav')
        self.assertIsNotNone(target)
        self.assertEqual(target.parent, AI_OUTPUT_DIR.resolve())
        self.assertEqual(target.name, 'sample.wav')

    def test_resolve_artifact_path_rejects_traversal(self):
        target = self.server._resolve_artifact_path('../../secret.wav')
        self.assertIsNone(target)

    def test_resolve_artifact_path_rejects_extension(self):
        target = self.server._resolve_artifact_path('evil.exe')
        self.assertIsNone(target)

    def test_parse_bounded_int_success(self):
        with self.app.app_context():
            value, error = self.server._parse_bounded_int('30', 'days', 1, 365, 7)
            self.assertEqual(value, 30)
            self.assertIsNone(error)

    def test_parse_bounded_int_invalid_type(self):
        with self.app.app_context():
            value, error = self.server._parse_bounded_int('abc', 'days', 1, 365, 7)
            self.assertIsNone(value)
            self.assertIsNotNone(error)
            self.assertEqual(error[1], 400)

    def test_parse_bounded_float_out_of_range(self):
        with self.app.app_context():
            value, error = self.server._parse_bounded_float('-1', 'initial_balance', 1, 100, 10)
            self.assertIsNone(value)
            self.assertIsNotNone(error)
            self.assertEqual(error[1], 400)

    def test_validate_bank(self):
        with self.app.app_context():
            self.assertIsNone(self.server._validate_bank('zheshang'))
            error = self.server._validate_bank('unknown')
            self.assertIsNotNone(error)
            self.assertEqual(error[1], 400)


if __name__ == '__main__':
    unittest.main()
