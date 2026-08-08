"""雑談は一度きり（再利用禁止）の単体テスト。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
from value_posts import (
    chitchat_pool,
    is_chitchat_id,
    is_oneshot_value_id,
    unused_chitchat_posts,
    used_chitchat_ids,
)


class ChitchatOneShotTests(unittest.TestCase):
    def test_is_chitchat_id(self) -> None:
        self.assertTrue(is_chitchat_id(chitchat_pool()[0].value_id))
        self.assertFalse(is_chitchat_id("chat-repeat"))  # tip pool

    def test_ask_ids_are_oneshot(self) -> None:
        self.assertTrue(is_oneshot_value_id("ask-abc123"))
        self.assertTrue(is_oneshot_value_id("chat-summer-kakigori"))

    def test_used_ids_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "posted.json"
            first = chitchat_pool()[0].value_id
            second = chitchat_pool()[1].value_id
            ledger.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "item_code": f"value:{first}",
                                "kind": "chitchat",
                                "posted_on": "2026-08-01",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            used = used_chitchat_ids(ledger)
            self.assertEqual(used, {first})
            unused = unused_chitchat_posts(ledger)
            self.assertTrue(all(p.value_id != first for p in unused))
            self.assertTrue(any(p.value_id == second for p in unused))


if __name__ == "__main__":
    unittest.main()
