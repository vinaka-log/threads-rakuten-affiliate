"""ジブリ大喜利枠の単体テスト。"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
from composer import compose_ogiri
from ogiri_posts import OGIRI_POSTS, pick_ogiri
from value_posts import is_oneshot_value_id


class OgiriSlotTests(unittest.TestCase):
    def test_slots_and_pool(self) -> None:
        self.assertEqual(config.OGIRI_SLOTS, (2, 6))
        self.assertGreaterEqual(len(OGIRI_POSTS), 10)
        for row in OGIRI_POSTS:
            self.assertTrue(str(row["id"]).startswith("ogiri-"))
            self.assertTrue(str(row["image_url"]).startswith("https://www.ghibli.jp/gallery/"))
            self.assertNotIn("http", str(row["text"]).lower())
            self.assertNotIn("PR", str(row["text"]))

    def test_compose_has_image(self) -> None:
        for slot in config.OGIRI_SLOTS:
            composed = compose_ogiri(date(2026, 8, 8), slot)
            self.assertTrue(composed.item_code.startswith("value:ogiri-"))
            self.assertTrue(composed.image_url.startswith("https://www.ghibli.jp/gallery/"))
            self.assertEqual(len(composed.texts), 1)
            self.assertTrue(is_oneshot_value_id(composed.item_code.split(":", 1)[-1]))

    def test_pick_skips_used(self) -> None:
        first = pick_ogiri(extra_used=set())
        second = pick_ogiri(extra_used={str(first["id"])})
        self.assertNotEqual(first["id"], second["id"])


if __name__ == "__main__":
    unittest.main()
