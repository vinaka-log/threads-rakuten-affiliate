"""問いかけ型雑談（公式4択アンケート）の単体テスト。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
from ask_chitchat import (
    _soften_trend_topic,
    generate_ask_posts,
    pick_ask_post,
    save_pool,
    unused_ask_posts,
    used_ask_ids,
)


class SoftenTrendTests(unittest.TestCase):
    def test_baseball_result_short(self) -> None:
        self.assertEqual(
            _soften_trend_topic("【プロ野球結果】オリックスが楽天にサヨナラ勝ち"),
            "今日のプロ野球",
        )

    def test_ohtani(self) -> None:
        self.assertEqual(
            _soften_trend_topic("ドジャースが獲得を正式発表 大谷の復帰に影響なし"),
            "大谷選手の近況",
        )

    def test_heat(self) -> None:
        self.assertEqual(
            _soften_trend_topic("プロ野球2軍戦 新たな暑熱対策"),
            "今年の暑さ対策",
        )


class AskPoolTests(unittest.TestCase):
    def test_generate_without_network(self) -> None:
        with mock.patch("ask_chitchat.load_trend_seeds", return_value=["プロ野球結果 巨人勝利"]):
            with mock.patch(
                "ask_chitchat.refresh_trend_seeds",
                return_value=["プロ野球結果 巨人勝利"],
            ):
                posts = generate_ask_posts(6, existing_ids=set())
        self.assertGreaterEqual(len(posts), 4)
        for row in posts:
            text = row["text"]
            opts = row["options"]
            self.assertEqual(len(opts), 4)
            self.assertNotIn("http", text.lower())
            self.assertNotIn("※PR", text)
            self.assertTrue(all(1 <= len(o) <= 25 for o in opts))

    def test_used_ids_and_pick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pool_path = tmp_path / "ask_pool.json"
            ledger = tmp_path / "posted.json"
            items = [
                {
                    "id": "ask-aaa",
                    "text": "夏といえばアイス、推しは？",
                    "options": ["しろくまくん", "ガリガリ君", "ハーゲンダッツ", "その他"],
                    "source": "seed",
                },
                {
                    "id": "ask-bbb",
                    "text": "かき氷の味、どれ派？",
                    "options": ["いちご", "宇治金時", "レモン", "その他"],
                    "source": "seed",
                },
            ]
            save_pool({"items": items}, path=pool_path)
            ledger.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "item_code": "value:ask-aaa",
                                "kind": "ask-chitchat",
                                "posted_on": "2026-08-03",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            old_ledger = config.LEDGER_PATH
            old_pool = config.ASK_CHITCHAT_POOL_PATH
            try:
                config.LEDGER_PATH = ledger
                config.ASK_CHITCHAT_POOL_PATH = pool_path
                import ask_chitchat as ac

                old_ask = ac.ASK_POOL_PATH
                ac.ASK_POOL_PATH = pool_path
                used = used_ask_ids(ledger)
                self.assertEqual(used, {"ask-aaa"})
                unused = unused_ask_posts()
                self.assertEqual([u["id"] for u in unused], ["ask-bbb"])
                with mock.patch.object(ac, "ensure_ask_supply", return_value=0):
                    picked = pick_ask_post(slot_salt=1)
                self.assertEqual(picked["id"], "ask-bbb")
                self.assertEqual(len(picked["options"]), 4)
            finally:
                config.LEDGER_PATH = old_ledger
                config.ASK_CHITCHAT_POOL_PATH = old_pool
                ac.ASK_POOL_PATH = old_ask


class AskSlotsWiringTests(unittest.TestCase):
    def test_morning_slots_are_native_polls(self) -> None:
        from datetime import date
        from composer import compose_value
        from value_posts import is_ask_chitchat_id

        self.assertEqual(config.ASK_CHITCHAT_SLOTS, (0, 3, 7))
        for slot in (0, 3, 7):
            composed = compose_value(date(2026, 8, 7), slot)
            self.assertTrue(is_ask_chitchat_id(composed.item_code.split(":", 1)[1]))
            self.assertEqual(len(composed.poll_options), 4)


if __name__ == "__main__":
    unittest.main()
