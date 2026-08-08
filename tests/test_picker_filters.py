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

    def test_refill_bottle_blocked_for_detergent(self) -> None:
        item = _item(
            code="mon-o-tone:10000064",
            name="洗濯洗剤用詰め替えボトル",
            price=650,
            review_count=2783,
            review_average=4.5,
        )
        detergent = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
        self.assertTrue(is_blocked(item))
        self.assertFalse(passes_quality(item))
        filtered = _filter_candidates([item], used=set(), pain=detergent)
        self.assertEqual(filtered, [])

    def test_softener_perfume_like_word_not_blocked(self) -> None:
        """「香水調」「アットコスメ」だけで柔軟剤を落とさない。"""
        item = _item(
            code="soft:1",
            name="ファーファ 液体 柔軟剤 香水調 クリスタルムスク 詰め替え 1440ml アットコスメ",
            price=1980,
            review_count=250,
            review_average=4.5,
        )
        softener = next(p for p in config.PAIN_INTENTS if p.id == "softener")
        self.assertFalse(is_blocked(item))
        self.assertTrue(passes_quality(item))
        self.assertTrue(_matches_pain(item, softener))

    def test_detergent_under_3000_ok(self) -> None:
        item = _item(
            code="shop:1",
            name="アタック 液体洗剤 つめかえ用 2900g",
            price=1980,
        )
        detergent = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
        self.assertFalse(is_blocked(item))
        self.assertTrue(passes_quality(item))
        self.assertTrue(_matches_pain(item, detergent))
        filtered = _filter_candidates([item], used=set(), pain=detergent)
        self.assertEqual(filtered, [item])

    def test_bleach_rejected_for_detergent(self) -> None:
        item = _item(
            code="daily-shop:10000211",
            name="ワイドハイターEXパワー 4.5L 詰め替え用 業務用 衣料用漂白剤 洗濯洗剤 つめかえ",
            price=2650,
            review_count=367,
            review_average=4.8,
        )
        detergent = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
        self.assertFalse(_matches_pain(item, detergent))
        filtered = _filter_candidates([item], used=set(), pain=detergent)
        self.assertEqual(filtered, [])

    def test_detergent_storage_rejected(self) -> None:
        item = _item(
            code="roomy:10014969",
            name="マグネット洗濯洗剤ボールストッカー タワー 山崎実業 詰め替え用 洗面所収納",
            price=2420,
            review_count=536,
            review_average=4.8,
        )
        detergent = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
        self.assertTrue(is_blocked(item) or not _matches_pain(item, detergent))
        filtered = _filter_candidates([item], used=set(), pain=detergent)
        self.assertEqual(filtered, [])

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

    def test_toilet_paper_pack_ok_case_rejected(self) -> None:
        tp = next(p for p in config.PAIN_INTENTS if p.id == "toilet-paper")
        pack = _item(
            code="tp:pack",
            name="ネピア トイレットペーパー ダブル 30m 12ロール",
            price=1280,
        )
        elleair = _item(
            code="tp:elleair",
            name="エリエール トイレットティシュー コンパクト ダブル 82.5m 8ロール ケース",
            price=1980,
        )
        case = _item(
            code="tp:case",
            name="ティッシュケース トイレットペーパー ペーパーポット カバー",
            price=2970,
            review_count=11888,
            review_average=4.7,
        )
        self.assertTrue(_matches_pain(pack, tp))
        self.assertTrue(_matches_pain(elleair, tp))
        self.assertFalse(_matches_pain(case, tp))
        self.assertEqual(
            _filter_candidates([case, pack, elleair], used=set(), pain=tp),
            [pack, elleair],
        )

    def test_tissue_pack_ok_case_rejected(self) -> None:
        tissue = next(p for p in config.PAIN_INTENTS if p.id == "tissue")
        pack = _item(
            code="ti:pack",
            name="ネピア ボックスティッシュ 200組×5個パック",
            price=470,
        )
        soft = _item(
            code="ti:soft",
            name="エリエール ティシュー ソフトパック 150組×5",
            price=890,
        )
        case = _item(
            code="ti:case",
            name="おしゃれ ティッシュケース ボックス型 収納",
            price=1980,
        )
        self.assertTrue(_matches_pain(pack, tissue))
        self.assertTrue(_matches_pain(soft, tissue))
        self.assertFalse(_matches_pain(case, tissue))
        filtered = _filter_candidates([case, pack, soft], used=set(), pain=tissue)
        self.assertEqual(filtered, [pack, soft])

    def test_postage_included_preferred_over_separate(self) -> None:
        from picker import is_postage_included

        detergent = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
        paid = _item(
            code="det:paid",
            name="アタック 液体洗剤 つめかえ用 2900g",
            price=1980,
            review_count=500,
        )
        # dataclass replace postage via object.__new__ pattern - rebuild
        paid = RakutenItem(
            item_code="det:paid",
            item_name="アタック 液体洗剤 つめかえ用 2900g",
            item_price=1980,
            affiliate_url="https://example.com/a",
            item_url="https://example.com/i",
            review_average=4.5,
            review_count=500,
            shop_name="test",
            genre_id="100939",
            postage_flag=1,  # 送料別
        )
        free = RakutenItem(
            item_code="det:free",
            item_name="アタック 液体洗剤 つめかえ用 2500g",
            item_price=2100,
            affiliate_url="https://example.com/a",
            item_url="https://example.com/i",
            review_average=4.5,
            review_count=200,  # 件数は少なくても送料込を優先
            shop_name="test",
            genre_id="100939",
            postage_flag=0,  # 送料込
        )
        self.assertFalse(is_postage_included(paid))
        self.assertTrue(is_postage_included(free))
        filtered = _filter_candidates([paid, free], used=set(), pain=detergent)
        self.assertEqual([i.item_code for i in filtered], ["det:free"])

    def test_timesave_slot_optional(self) -> None:
        """時短専用枠が空でも通常商品枠で運用できる。"""
        from datetime import date
        from picker import pain_for_slot

        self.assertEqual(config.TIMESAVE_ITEM_SLOTS, ())
        self.assertEqual(config.ITEM_SLOTS, (5, 9))
        on = date(2026, 8, 3)
        pain = pain_for_slot(5, on)
        # all_pain_intents ローテに時短専用も含む
        self.assertIn(pain.id, {p.id for p in config.all_pain_intents()})

    def test_floor_wiper_sheet_ok_body_rejected(self) -> None:
        pain = next(p for p in config.all_pain_intents() if p.id == "floor-wiper")
        sheet = _item(
            code="fw:sheet",
            name="クイックルワイパー 取り替え用ドライシート 40枚",
            price=680,
        )
        wet = _item(
            code="fw:wet",
            name="クイックルワイパー 立体吸着ウエットシート 32枚",
            price=520,
        )
        body = _item(
            code="fw:body",
            name="クイックルワイパー 本体セット フロア用ハンドル",
            price=980,
        )
        self.assertTrue(_matches_pain(sheet, pain))
        self.assertTrue(_matches_pain(wet, pain))
        self.assertFalse(_matches_pain(body, pain))

    def test_single_item_slot_rotates_across_days(self) -> None:
        """商品枠でも日付で悩みが回る。"""
        from datetime import date
        from picker import pain_for_slot

        ids = [pain_for_slot(5, date(2026, 8, d)).id for d in range(1, 12)]
        self.assertGreaterEqual(len(set(ids)), 5)


if __name__ == "__main__":
    unittest.main()
