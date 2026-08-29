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
    _SOFT_LINK_LIMIT,
    _SOFT_MAIN_LIMIT,
    _SOFT_MEMO_LIMIT,
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
            "ベビーカー レインカバー 折りたたみタイプ",
        ),
        item_price=kwargs.get("price", 1980),
        affiliate_url="https://example.com/aff",
        item_url="https://example.com/item",
        review_average=4.5,
        review_count=200,
        shop_name="test-shop",
        genre_id="100533",
        postage_flag=0,
        rank=3,
    )
    pain = next(p for p in config.PAIN_INTENTS if p.id == "stroller-rain")
    return PickResult(
        item=item,
        genre=config.GENRES[0],
        slot=5,
        posted_on="2026-08-06",
        pain=pain,
    )


class ItemCopyStructureTests(unittest.TestCase):
    def test_legacy_template_ids_resolve(self) -> None:
        self.assertEqual(_resolve_template_id("hook-benefit"), "hook-must")
        self.assertEqual(_resolve_template_id("hook-must"), "hook-must")

    def test_main_hides_product_and_price(self) -> None:
        composed = compose(_pick(), template_id="hook-must")
        main, memo, link = composed.texts
        self.assertNotIn("円", main)
        self.assertNotIn("レビュー", main)
        self.assertNotIn("「", main)
        self.assertNotIn("」", main)
        self.assertNotIn("レインカバー", main)
        self.assertNotIn("おすすめ", main)
        self.assertNotIn("コスパ", main)
        self.assertLessEqual(len(main), _SOFT_MAIN_LIMIT)
        self.assertTrue(
            any(k in main for k in ("？", "教えて", "どうしてる", "いる？")),
            msg=main,
        )

    def test_main_has_rami_style_hook_and_after_benefit(self) -> None:
        pain = next(p for p in config.PAIN_INTENTS if p.id == "stroller-rain")
        for tid, _ in _MAIN_TEMPLATES:
            composed = compose(_pick(), template_id=tid)
            main, memo, _link = composed.texts
            self.assertTrue(main.startswith("↓"), msg=f"{tid}: {main}")
            self.assertIn("＼", main, msg=f"{tid}: {main}")
            self.assertIn(pain.benefit, main, msg=f"{tid}: {main}")
            self.assertIn("揃えてからの方が楽", memo)

    def test_all_templates_stay_short(self) -> None:
        for tid, _ in _MAIN_TEMPLATES:
            composed = compose(_pick(), template_id=tid)
            main, memo, link = composed.texts
            self.assertLessEqual(len(main), _SOFT_MAIN_LIMIT, msg=f"{tid} main too long: {main}")
            self.assertLessEqual(len(memo), _SOFT_MEMO_LIMIT, msg=f"{tid} memo too long")
            self.assertLessEqual(len(link), _SOFT_LINK_LIMIT, msg=f"{tid} link too long")
            self.assertNotIn("「", main)
            self.assertIn("うちの候補はこれ", memo)
            self.assertIn("レインカバー", memo)
            self.assertNotIn("http", memo.lower())
            self.assertNotIn(_PR_DISCLOSURE, memo)
            self.assertNotIn("円", memo)

    def test_link_has_url_and_disclosure(self) -> None:
        composed = compose(_pick(), template_id="hook-must")
        main, memo, link = composed.texts
        self.assertIn("https://example.com/aff", link)
        self.assertTrue(link.rstrip().endswith(_PR_DISCLOSURE))
        self.assertNotIn("アフィリエイト", link)
        self.assertNotIn("test-shop", link)
        _validate(composed.texts)

    def test_pain_copy_length_budget(self) -> None:
        for pain in config.PAIN_INTENTS:
            self.assertLessEqual(len(pain.problem), 32, msg=pain.id)
            self.assertLessEqual(len(pain.benefit), 28, msg=pain.id)
            self.assertLessEqual(len(pain.avoid), 28, msg=pain.id)
            self.assertLessEqual(len(pain.scene), 24, msg=pain.id)

    def test_rain_cover_matches_stroller_rain(self) -> None:
        pain = next(p for p in config.PAIN_INTENTS if p.id == "stroller-rain")
        item = _pick().item
        self.assertTrue(_matches_pain(item, pain))
