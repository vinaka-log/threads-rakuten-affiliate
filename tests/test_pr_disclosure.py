"""リンクリプの PR 表記フォーマット単体テスト。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
from composer import _PR_DISCLOSURE, _REPLY_TEMPLATE, _validate, compose
from picker import PickResult
from rakuten import RakutenItem


class PrDisclosureTests(unittest.TestCase):
    def test_reply_template_ends_with_new_disclosure(self) -> None:
        self.assertIn("▼商品はこちら", _REPLY_TEMPLATE)
        self.assertTrue(_REPLY_TEMPLATE.rstrip().endswith(_PR_DISCLOSURE))
        self.assertNotIn("#PR", _REPLY_TEMPLATE)
        self.assertNotIn("アフィリエイトリンクを含みます", _REPLY_TEMPLATE)

    def test_validate_requires_disclosure_phrase(self) -> None:
        main = "洗剤、また切れそう？\n\nみんなはどうしてる？"
        reply_ok = (
            "正体はこれ。\n"
            "【テスト商品】\n"
            "▼商品はこちら\n"
            "https://example.com/a\n"
            "\n※PR（アフィリエイトリンク）"
        )
        _validate([main, reply_ok])
        with self.assertRaises(ValueError):
            _validate([main, "#PR\nアフィリエイトリンクを含みます\nhttps://example.com/a"])

    def test_compose_includes_new_disclosure(self) -> None:
        item = RakutenItem(
            item_code="shop:1",
            item_name="アタック 液体洗剤 つめかえ用 2900g",
            item_price=1980,
            affiliate_url="https://example.com/aff",
            item_url="https://example.com/item",
            review_average=4.5,
            review_count=200,
            shop_name="test-shop",
            genre_id="100939",
            postage_flag=0,
        )
        pain = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
        pick = PickResult(
            item=item,
            genre=config.GENRES[0],
            slot=7,
            posted_on="2026-08-06",
            pain=pain,
        )
        composed = compose(pick)
        self.assertEqual(len(composed.texts), 2)
        self.assertNotIn("http", composed.texts[0])
        self.assertNotIn("「", composed.texts[0])
        self.assertIn("正体はこれ", composed.texts[1])
        self.assertIn("https://example.com/aff", composed.texts[1])
        self.assertIn(_PR_DISCLOSURE, composed.texts[1])
        self.assertFalse(composed.texts[1].lstrip().startswith("#PR"))


if __name__ == "__main__":
    unittest.main()
