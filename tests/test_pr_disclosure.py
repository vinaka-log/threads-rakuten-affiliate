"""リンクリプの PR 表記フォーマット単体テスト。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
from composer import _PR_DISCLOSURE, _REPLY_LINK, _REPLY_MEMO, _validate, compose
from picker import PickResult
from rakuten import RakutenItem


class PrDisclosureTests(unittest.TestCase):
    def test_reply_template_ends_with_new_disclosure(self) -> None:
        self.assertTrue(_REPLY_LINK.rstrip().endswith(_PR_DISCLOSURE))
        self.assertNotIn("▼商品はこちら", _REPLY_LINK)
        self.assertNotIn("正体はこれ", _REPLY_MEMO)
        self.assertNotIn("#PR", _REPLY_LINK)
        self.assertNotIn("アフィリエイト", _REPLY_LINK)
        self.assertNotIn("アフィリエイト", _REPLY_MEMO)

    def test_validate_requires_disclosure_phrase(self) -> None:
        main = "急な雨、ベビーカーどうしてる？\n\nみんなはどうしてる？"
        memo = "うちの候補はこれ。\nテスト商品"
        reply_ok = f"https://example.com/a\n{_PR_DISCLOSURE}"
        _validate([main, memo, reply_ok])
        with self.assertRaises(ValueError):
            _validate([main, memo, "#PR\nアフィリエイトリンクを含みます\nhttps://example.com/a"])
        with self.assertRaises(ValueError):
            _validate([main, f"{memo}\nhttps://example.com/a", reply_ok])

    def test_compose_includes_new_disclosure(self) -> None:
        item = RakutenItem(
            item_code="shop:1",
            item_name="ベビーカー レインカバー 折りたたみタイプ",
            item_price=1980,
            affiliate_url="https://example.com/aff",
            item_url="https://example.com/item",
            review_average=4.5,
            review_count=200,
            shop_name="test-shop",
            genre_id="100533",
            postage_flag=0,
        )
        pain = next(p for p in config.PAIN_INTENTS if p.id == "stroller-rain")
        pick = PickResult(
            item=item,
            genre=config.GENRES[0],
            slot=5,
            posted_on="2026-08-06",
            pain=pain,
        )
        composed = compose(pick)
        self.assertEqual(len(composed.texts), 3)
        main, memo, link = composed.texts
        self.assertNotIn("http", main.lower())
        self.assertNotIn("http", memo.lower())
        self.assertNotIn("「", main)
        self.assertIn("うちの候補はこれ", memo)
        self.assertIn("https://example.com/aff", link)
        self.assertIn(_PR_DISCLOSURE, link)
        self.assertTrue(link.rstrip().endswith(_PR_DISCLOSURE))
        self.assertFalse(link.lstrip().startswith("#PR"))
        self.assertNotIn("アフィリエイト", "\n".join(composed.texts))


if __name__ == "__main__":
    unittest.main()
