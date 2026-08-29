"""楽天商品URLパースとディープリンク組み立ての単体テスト。"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from rakuten import RakutenClient


class RakutenUrlParseTests(unittest.TestCase):
    def test_parse_item_url_strips_query(self) -> None:
        got = RakutenClient.parse_item_url(
            "https://item.rakuten.co.jp/plaisiureux/pl_65/?s-id=bk_pc_item_list_name_n"
        )
        self.assertEqual(got, ("plaisiureux", "pl_65"))

    def test_parse_item_url_requires_shop_and_code(self) -> None:
        self.assertIsNone(RakutenClient.parse_item_url("https://www.rakuten.co.jp/"))
        self.assertIsNone(RakutenClient.parse_item_url(""))

    def test_deep_affiliate_url(self) -> None:
        env = {
            "RAKUTEN_APPLICATION_ID": "00000000-0000-0000-0000-000000000001",
            "RAKUTEN_ACCESS_KEY": "test-access-key",
            "RAKUTEN_AFFILIATE_ID": "aff.test.id",
        }
        with patch.dict(os.environ, env, clear=False):
            client = RakutenClient()
            url = client.deep_affiliate_url(
                "https://item.rakuten.co.jp/plaisiureux/pl_65/?s-id=x"
            )
        self.assertTrue(url.startswith("https://hb.afl.rakuten.co.jp/aff.test.id/?"))
        self.assertIn("pc=https%3A%2F%2Fitem.rakuten.co.jp%2Fplaisiureux%2Fpl_65%2F", url)
        self.assertIn("m=https%3A%2F%2Fitem.rakuten.co.jp%2Fplaisiureux%2Fpl_65%2F", url)


if __name__ == "__main__":
    unittest.main()
