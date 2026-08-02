"""商品マッチ・価格・ブロックフィルタの単体テスト（ネットワーク不要）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
from picker import _filter_candidates, _name_matches, is_blocked, passes_quality
from rakuten import RakutenItem


def _item(
    *,
    code: str,
    name: str,
    price: int,
    review_count: int = 200,
    review_average: float = 4.5,
) -> RakutenItem:
    return RakutenItem(
        item_code=code,
        item_name=name,
        item_price=price,
        affiliate_url="https://example.com/a",
        item_url="https://example.com/i",
        review_average=review_average,
        review_count=review_count,
        shop_name="test",
        genre_id="100939",
    )


class PickerFilterTests(unittest.TestCase):
    def test_lancome_not_usable_as_detergent(self) -> None:
        item = _item(
            code="lancome:10000136",
            name="【公式】ジェニフィック アルティメ セラム / 50mL / 美容液 / ランコム",
            price=14850,
            review_count=200,
            review_average=4.8,
        )
        detergent = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
        self.assertTrue(is_blocked(item))
        self.assertFalse(passes_quality(item))
        self.assertFalse(_name_matches(item, detergent.name_hints))
        filtered = _filter_candidates([item], used=set(), pain=detergent)
        self.assertEqual(filtered, [])

    def test_detergent_under_3000_ok(self) -> None:
        item = _item(
            code="shop:1",
            name="アタック 洗濯洗剤 詰め替え 超特大",
            price=1980,
        )
        detergent = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
        self.assertFalse(is_blocked(item))
        self.assertTrue(passes_quality(item))
        self.assertTrue(_name_matches(item, detergent.name_hints))
        filtered = _filter_candidates([item], used=set(), pain=detergent)
        self.assertEqual(filtered, [item])

    def test_price_over_3000_rejected(self) -> None:
        item = _item(
            code="shop:2",
            name="洗濯洗剤 業務用ケース",
            price=4500,
        )
        self.assertFalse(passes_quality(item))

    def test_low_review_average_rejected(self) -> None:
        item = _item(
            code="shop:3",
            name="キッチンペーパー 2倍巻き",
            price=980,
            review_average=4.1,
        )
        self.assertFalse(passes_quality(item))

    def test_no_soft_fallback_to_unrelated(self) -> None:
        """悩み不一致の高評価・低価格品だけでも候補に残さない。"""
        other = _item(
            code="tp:1",
            name="トイレットペーパー ダブル 12ロール",
            price=1490,
            review_average=4.6,
        )
        detergent = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
        self.assertTrue(passes_quality(other))
        self.assertFalse(_name_matches(other, detergent.name_hints))
        filtered = _filter_candidates([other], used=set(), pain=detergent)
        self.assertEqual(filtered, [])


if __name__ == "__main__":
    unittest.main()
