"""Threads公式4択アンケート（poll_attachment）の単体テスト。"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
from ask_chitchat import (
    generate_ask_posts,
    normalize_poll_options,
    pick_ask_post,
)
from composer import compose_value
from threads_client import _poll_attachment_payload
from value_posts import is_ask_chitchat_id, pick_value_post


class PollPayloadTests(unittest.TestCase):
    def test_payload_has_four_options(self) -> None:
        raw = _poll_attachment_payload(["しろくまくん", "ガリガリ君", "ハーゲンダッツ", "その他"])
        data = json.loads(raw)
        self.assertEqual(
            data,
            {
                "option_a": "しろくまくん",
                "option_b": "ガリガリ君",
                "option_c": "ハーゲンダッツ",
                "option_d": "その他",
            },
        )

    def test_option_clipped_to_25(self) -> None:
        long = "あ" * 30
        data = json.loads(_poll_attachment_payload([long, "B", "C", "D"]))
        self.assertEqual(len(data["option_a"]), 25)

    def test_normalize_pads_to_four(self) -> None:
        opts = normalize_poll_options(["麦茶", "水"])
        self.assertEqual(len(opts), 4)
        self.assertTrue(all(1 <= len(o) <= 25 for o in opts))


class NativePollAskTests(unittest.TestCase):
    def test_generate_posts_include_options(self) -> None:
        with mock.patch("ask_chitchat.load_trend_seeds", return_value=[]):
            with mock.patch("ask_chitchat.refresh_trend_seeds", return_value=[]):
                posts = generate_ask_posts(4, existing_ids=set())
        self.assertGreaterEqual(len(posts), 2)
        for row in posts:
            self.assertEqual(len(row["options"]), 4)
            self.assertTrue(all(len(o) <= 25 for o in row["options"]))
            self.assertNotIn("http", row["text"].lower())

    def test_slots_compose_with_poll(self) -> None:
        self.assertEqual(config.ASK_CHITCHAT_SLOTS, (0, 3, 7))
        for slot in (0, 3, 7):
            composed = compose_value(date(2026, 8, 7), slot)
            self.assertTrue(composed.item_code.startswith("value:ask-"))
            self.assertEqual(len(composed.poll_options), 4)
            self.assertTrue(all(len(o) <= 25 for o in composed.poll_options))
            picked = pick_value_post(date(2026, 8, 7), slot)
            self.assertTrue(is_ask_chitchat_id(picked.value_id))
            self.assertEqual(len(picked.poll_options), 4)


if __name__ == "__main__":
    unittest.main()
