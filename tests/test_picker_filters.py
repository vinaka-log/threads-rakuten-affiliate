"""商品マッチ・価格・ブロックフィルタの単体テスト（ネットワーク不要）。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
from picker import (
    _filter_candidates,
    _matches_pain,
    _name_matches,
    is_blocked,
    passes_quality,
)
from rakuten import RakutenItem


def _item(
    *,
    code: str,
    name: str,
    price: int,
    review_count: int = 200,
    review_average: float = 4.5,
    postage_flag: int = 0,
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
        genre_id="100533",
        postage_flag=postage_flag,
    )


class PickerFilterTests(unittest.TestCase):
    def test_cosmetics_blocked(self) -> None:
        item = _item(
            code="lancome:1",
            name="【公式】ジェニフィック アルティメ セラム / 50mL / 美容液 / ランコム",
            price=14850,
        )
        self.assertTrue(is_blocked(item))
        rain = next(p for p in config.PAIN_INTENTS if p.id == "stroller-rain")
        filtered = _filter_candidates([item], used=set(), pain=rain)
        self.assertEqual(filtered, [])

    def test_rain_cover_matches(self) -> None:
        item = _item(
            code="fabomi:1",
            name="【楽天1位】ベビーカー レインカバー 折りたたみタイプ",
            price=1980,
        )
        rain = next(p for p in config.PAIN_INTENTS if p.id == "stroller-rain")
        self.assertTrue(_matches_pain(item, rain))
        filtered = _filter_candidates([item], used=set(), pain=rain)
        self.assertEqual(filtered, [item])

    def test_adult_rain_excluded(self) -> None:
        item = _item(
            code="x:1",
            name="大人用 レインカバー 自転車",
            price=1980,
        )
        rain = next(p for p in config.PAIN_INTENTS if p.id == "stroller-rain")
        self.assertFalse(_matches_pain(item, rain))

    def test_baby_pillow_under_limit(self) -> None:
        item = _item(
            code="sanho:1",
            name="ベビー枕 ジオピロー 公式 新生児から使える",
            price=7980,
        )
        pillow = next(p for p in config.PAIN_INTENTS if p.id == "baby-pillow")
        self.assertTrue(_matches_pain(item, pillow))
        self.assertTrue(passes_quality(item, max_price=pillow.max_price))
        filtered = _filter_candidates([item], used=set(), pain=pillow)
        self.assertEqual(filtered, [item])

    def test_diaper_stocker_ok(self) -> None:
        item = _item(
            code="rise:1",
            name="おむつストッカー 収納 オムツストッカー",
            price=2230,
        )
        stock = next(p for p in config.PAIN_INTENTS if p.id == "diaper-stock")
        self.assertTrue(_matches_pain(item, stock))
        # 旧ペルソナではストッカー除外だったが、ベビーでは採用する
        self.assertFalse(is_blocked(item))

    def test_diapers_exclude_stocker(self) -> None:
        item = _item(
            code="x:2",
            name="おむつストッカー 収納ケース",
            price=2230,
        )
        diapers = next(p for p in config.PAIN_INTENTS if p.id == "diapers")
        self.assertFalse(_matches_pain(item, diapers))

    def test_prefer_postage_included(self) -> None:
        rain = next(p for p in config.PAIN_INTENTS if p.id == "stroller-rain")
        paid = _item(
            code="a:1",
            name="ベビーカー レインカバー A",
            price=2000,
            review_count=500,
            postage_flag=1,
        )
        free = _item(
            code="b:1",
            name="ベビーカー レインカバー B",
            price=2100,
            review_count=200,
            postage_flag=0,
        )
        filtered = _filter_candidates([paid, free], used=set(), pain=rain)
        self.assertEqual(filtered[0].item_code, "b:1")

    def test_all_pain_ids_unique(self) -> None:
        ids = [p.id for p in config.all_pain_intents()]
        self.assertEqual(len(ids), len(set(ids)))
        for pain in config.PAIN_INTENTS:
            self.assertIn(pain.id, {p.id for p in config.all_pain_intents()})


if __name__ == "__main__":
    unittest.main()
