"""商品投稿テンプレ（本投稿・リプ）の構成テスト。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
from composer import (
    _PR_DISCLOSURE,
    _REPLY_TEMPLATE,
    _resolve_template_id,
    _validate,
    compose,
)
from picker import PickResult
from rakuten import RakutenItem


def _pick(**kwargs) -> PickResult:
    item = RakutenItem(
        item_code=kwargs.get("code", "shop:1"),
        item_name=kwargs.get(
            "name",
            "アタック 液体洗剤 つめかえ用 2900g 超特大",
        ),
        item_price=kwargs.get("price", 1980),
        affiliate_url="https://example.com/aff",
        item_url="https://example.com/item",
        review_average=4.5,
        review_count=200,
        shop_name="test-shop",
        genre_id="100939",
        postage_flag=0,
    )
    pain = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
    return PickResult(
        item=item,
        genre=config.GENRES[0],
        slot=6,
        posted_on="2026-08-03",
        pain=pain,
    )


class ItemCopyStructureTests(unittest.TestCase):
    def test_legacy_template_ids_resolve(self) -> None:
        self.assertEqual(_resolve_template_id("hook-benefit"), "hook-must")
        self.assertEqual(_resolve_template_id("hook-must"), "hook-must")

    def test_main_has_no_price_or_labels(self) -> None:
        composed = compose(_pick(), template_id="hook-must")
        main, reply = composed.texts
        self.assertNotIn("円", main)
        self.assertNotIn("レビュー", main)
        self.assertNotIn("このままだと:", main)
        self.assertNotIn("Before:", main)
        self.assertIn("リプ", main)
        self.assertLessEqual(len(main), 280)

    def test_reply_is_short_and_ends_with_disclosure(self) -> None:
        composed = compose(_pick(), template_id="hook-honest")
        reply = composed.texts[1]
        self.assertIn("正直なところ", reply)
        self.assertIn("▼商品はこちら", reply)
        self.assertIn("https://example.com/aff", reply)
        self.assertTrue(reply.rstrip().endswith(_PR_DISCLOSURE))
        self.assertNotIn("・悩み:", reply)
        self.assertNotIn("・困り事:", reply)
        self.assertLessEqual(len(reply), 420)

    def test_pains_rotate_templates(self) -> None:
        """悩み側で template_id を固定しない（単調なAI感を避ける）。"""
        fixed = [p for p in config.all_pain_intents() if p.template_id]
        self.assertEqual(fixed, [])

    def test_validate_rejects_old_style_main(self) -> None:
        with self.assertRaises(ValueError):
            _validate(
                [
                    "洗剤切れ？\n\nこのままだと: 困る\nこれを置くと: 助かる",
                    f"▼商品はこちら\nhttps://example.com/a\n\n{_PR_DISCLOSURE}",
                ]
            )


if __name__ == "__main__":
    unittest.main()
