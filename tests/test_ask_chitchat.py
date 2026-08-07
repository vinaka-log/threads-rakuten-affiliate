"""問いかけ型雑談（季節 + 軽いトレンド）の単体テスト。"""

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
    load_pool,
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
            with mock.patch("ask_chitchat.refresh_trend_seeds", return_value=["プロ野球結果 巨人勝利"]):
                posts = generate_ask_posts(6, existing_ids=set())
        self.assertGreaterEqual(len(posts), 4)
        for row in posts:
            text = row["text"]
            self.assertIn("🐻‍❄️", text)
            self.assertNotIn("http", text.lower())
            self.assertNotIn("※PR", text)
            self.assertLessEqual(len(text), 140)

    def test_used_ids_and_pick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pool_path = tmp_path / "ask_pool.json"
            ledger = tmp_path / "posted.json"
            items = [
                {
                    "id": "ask-aaa",
                    "text": "夏といえばアイスだよね🍨 みんなのオススメ教えて〜 僕はしろくまくん🐻‍❄️",
                    "source": "seed",
                },
                {
                    "id": "ask-bbb",
                    "text": "夏といえばかき氷だよね🍧 みんなのオススメ教えて〜 僕はいちご一択🐻‍❄️",
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
                # module-level paths were bound at import; patch those too
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
            finally:
                config.LEDGER_PATH = old_ledger
                config.ASK_CHITCHAT_POOL_PATH = old_pool
                ac.ASK_POOL_PATH = old_ask


class AskSlotsWiringTests(unittest.TestCase):
    def test_morning_slots_are_ask_surveys(self) -> None:
        from datetime import date
        from value_posts import is_ask_chitchat_id, pick_value_post

        self.assertEqual(config.ASK_CHITCHAT_SLOTS, (0, 1))
        for slot in (0, 1):
            picked = pick_value_post(date(2026, 8, 7), slot)
            self.assertTrue(is_ask_chitchat_id(picked.value_id), msg=picked.value_id)
            self.assertTrue(
                any(k in picked.text for k in ("教えて", "どう思う", "何派", "いる？", "？")),
                msg=picked.text,
            )


if __name__ == "__main__":
    unittest.main()
