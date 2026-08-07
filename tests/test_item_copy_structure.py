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
    _MAIN_TEMPLATES,
    _PR_DISCLOSURE,
    _SOFT_MAIN_LIMIT,
    _SOFT_REPLY_LIMIT,
    _resolve_template_id,
    _validate,
    compose,
)
from picker import PickResult, _matches_pain
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
        rank=3,
    )
    pain = next(p for p in config.PAIN_INTENTS if p.id == "detergent")
    return PickResult(
        item=item,
        genre=config.GENRES[0],
        slot=2,
        posted_on="2026-08-06",
        pain=pain,
    )


class ItemCopyStructureTests(unittest.TestCase):
    def test_legacy_template_ids_resolve(self) -> None:
        self.assertEqual(_resolve_template_id("hook-benefit"), "hook-must")
        self.assertEqual(_resolve_template_id("hook-must"), "hook-must")

    def test_main_hides_product_and_price(self) -> None:
        composed = compose(_pick(), template_id="hook-must")
        main, reply = composed.texts
        self.assertNotIn("円", main)
        self.assertNotIn("レビュー", main)
        self.assertNotIn("「", main)
        self.assertNotIn("」", main)
        self.assertNotIn("アタック", main)
        self.assertNotIn("このままだと:", main)
        self.assertLessEqual(len(main), _SOFT_MAIN_LIMIT)
        # 返信を誘う問いかけ
        self.assertTrue(
            any(k in main for k in ("？", "教えて", "どうしてる", "いる？")),
            msg=main,
        )

    def test_all_templates_stay_short(self) -> None:
        for tid, _ in _MAIN_TEMPLATES:
            composed = compose(_pick(), template_id=tid)
            main, reply = composed.texts
            self.assertLessEqual(len(main), _SOFT_MAIN_LIMIT, msg=f"{tid} main too long")
            self.assertLessEqual(len(reply), _SOFT_REPLY_LIMIT, msg=f"{tid} reply too long")
            self.assertNotIn("「", main)
            self.assertIn("正体はこれ", reply)
            self.assertIn("アタック", reply)

    def test_reply_reveals_product_and_ends_with_disclosure(self) -> None:
        composed = compose(_pick(), template_id="hook-honest")
        main, reply = composed.texts
        self.assertIn("正体はこれ", reply)
        self.assertIn("正直、", reply)
        self.assertIn("▼商品はこちら", reply)
        self.assertIn("https://example.com/aff", reply)
        self.assertTrue(reply.rstrip().endswith(_PR_DISCLOSURE))
        self.assertNotIn("・悩み:", reply)
        benefit = next(p for p in config.PAIN_INTENTS if p.id == "detergent").benefit
        self.assertNotIn(benefit, reply)
        self.assertNotIn("test-shop", reply)
        self.assertLessEqual(len(reply), _SOFT_REPLY_LIMIT)

    def test_pain_copy_stays_compact(self) -> None:
        for pain in config.all_pain_intents():
            self.assertLessEqual(len(pain.problem), 32, msg=pain.id)
            self.assertLessEqual(len(pain.benefit), 28, msg=pain.id)
            self.assertLessEqual(len(pain.avoid), 28, msg=pain.id)
            self.assertLessEqual(len(pain.scene), 24, msg=pain.id)

    def test_pains_rotate_templates(self) -> None:
        fixed = [p for p in config.all_pain_intents() if p.template_id]
        self.assertEqual(fixed, [])

    def test_one_item_slot_per_day(self) -> None:
        self.assertEqual(config.POSTS_PER_DAY, 3)
        self.assertEqual(config.ITEM_SLOTS, (2,))
        self.assertEqual(config.ASK_CHITCHAT_SLOTS, (0, 1))
        self.assertEqual(config.STRUGGLE_SLOTS, ())
        self.assertEqual(config.CHITCHAT_SLOTS, ())
        self.assertNotIn(2, config.VALUE_SLOTS)

    def test_wrap_rejects_holder_gadgets(self) -> None:
        pain = next(p for p in config.PAIN_INTENTS if p.id == "wrap")
        holder = RakutenItem(
            item_code="wrap:holder",
            item_name="イデアコ ラップホルダー マグネット ideaco 22cm ラップケース サランラップ",
            item_price=2200,
            affiliate_url="https://example.com/a",
            item_url="https://example.com/i",
            review_average=4.3,
            review_count=171,
            shop_name="shop",
            genre_id="551167",
            postage_flag=0,
        )
        roll = RakutenItem(
            item_code="wrap:roll",
            item_name="サランラップ 22cm×50m 食品用ラップ",
            item_price=380,
            affiliate_url="https://example.com/a",
            item_url="https://example.com/i",
            review_average=4.6,
            review_count=800,
            shop_name="shop",
            genre_id="551167",
            postage_flag=0,
        )
        self.assertFalse(_matches_pain(holder, pain))
        self.assertTrue(_matches_pain(roll, pain))

    def test_floor_wiper_rejects_stand(self) -> None:
        pain = next(p for p in config.all_pain_intents() if p.id == "floor-wiper")
        stand = RakutenItem(
            item_code="fw:stand",
            item_name="山崎実業 フローリングワイパースタンド クイックルワイパー 収納",
            item_price=2500,
            affiliate_url="https://example.com/a",
            item_url="https://example.com/i",
            review_average=4.5,
            review_count=200,
            shop_name="shop",
            genre_id="100939",
            postage_flag=0,
        )
        sheet = RakutenItem(
            item_code="fw:sheet",
            item_name="クイックルワイパー 取り替え用ドライシート 40枚",
            item_price=680,
            affiliate_url="https://example.com/a",
            item_url="https://example.com/i",
            review_average=4.5,
            review_count=200,
            shop_name="shop",
            genre_id="100939",
            postage_flag=0,
        )
        self.assertFalse(_matches_pain(stand, pain))
        self.assertTrue(_matches_pain(sheet, pain))

    def test_validate_rejects_old_style_main(self) -> None:
        with self.assertRaises(ValueError):
            _validate(
                [
                    "洗剤切れ？\n\nこのままだと: 困る\nこれを置くと: 助かる",
                    f"正体はこれ。\n「x」\n\n▼商品はこちら\nhttps://example.com/a\n\n{_PR_DISCLOSURE}",
                ]
            )


if __name__ == "__main__":
    unittest.main()
