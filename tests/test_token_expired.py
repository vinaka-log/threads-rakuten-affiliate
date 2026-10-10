"""THREADS_ACCESS_TOKEN 期限切れ時のエラー整形。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from threads_client import ThreadsClient


class TokenExpiredErrorTests(unittest.TestCase):
    def test_detects_code_190(self) -> None:
        payload = {
            "error": {
                "message": "Error validating access token: Session has expired on Tuesday, 29-Sep-26 17:07:36 PDT.",
                "type": "OAuthException",
                "code": 190,
            }
        }
        self.assertTrue(ThreadsClient._is_token_expired_error(payload))
        msg = ThreadsClient._format_api_error("123/threads", payload)
        self.assertIn("THREADS_ACCESS_TOKEN 期限切れ", msg)
        self.assertIn("GitHub Secret", msg)

    def test_non_auth_error_unchanged_shape(self) -> None:
        payload = {"error": {"message": "Temporary", "code": 2}}
        self.assertFalse(ThreadsClient._is_token_expired_error(payload))
        msg = ThreadsClient._format_api_error("123/threads", payload)
        self.assertTrue(msg.startswith("API失敗 "))


if __name__ == "__main__":
    unittest.main()
