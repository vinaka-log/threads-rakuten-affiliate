"""長期トークン refresh の単体テスト。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refresh_token import TokenRefreshError, refresh_long_lived_token


class RefreshTokenTests(unittest.TestCase):
    def test_success_returns_access_token(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "access_token": "THAAW_NEW",
                    "token_type": "bearer",
                    "expires_in": 5184000,
                },
            )
        )
        with httpx.Client(transport=transport) as client:
            data = refresh_long_lived_token("THAAW_OLD", client=client)
        self.assertEqual(data["access_token"], "THAAW_NEW")
        self.assertEqual(data["expires_in"], 5184000)

    def test_expired_raises(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Session has expired",
                        "type": "OAuthException",
                        "code": 190,
                    }
                },
            )
        )
        with httpx.Client(transport=transport) as client:
            with self.assertRaises(TokenRefreshError) as ctx:
                refresh_long_lived_token("THAAW_OLD", client=client)
        self.assertIn("Session has expired", str(ctx.exception))

    def test_empty_token_raises(self) -> None:
        with self.assertRaises(TokenRefreshError):
            refresh_long_lived_token("")


if __name__ == "__main__":
    unittest.main()
