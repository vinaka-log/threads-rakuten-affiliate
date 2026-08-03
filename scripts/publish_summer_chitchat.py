"""One-shot: publish summer chitchat engagement posts (same style as ice cream hit).

Usage:
  python scripts/publish_summer_chitchat.py --which 1
  python scripts/publish_summer_chitchat.py --which 2

Only runs on TARGET_DATE (JST) unless --force.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from threads_client import ThreadsClient

JST = timezone(timedelta(hours=9))
TARGET_DATE = "2026-08-04"

# 伸びたアイス投稿と同型: 短い夏ネタ + みんなのオススメ募集 + 自分の回答(しろくま)
POSTS = {
    "1": (
        "chat-summer-kakigori-20260804",
        "夏といえばかき氷だよね🍧 みんなのオススメの味教えて〜 僕はいちご一択🐻‍❄️",
    ),
    "2": (
        "chat-summer-drink-20260804",
        "夏の飲み物、みんな何飲む？推し教えて〜 僕は麦茶一択、しろくまも麦茶派🐻‍❄️",
    ),
}


async def publish(text: str) -> list[str]:
    client = ThreadsClient(
        access_token=os.environ["THREADS_ACCESS_TOKEN"],
        user_id=os.environ["THREADS_USER_ID"],
    )
    result = await client.publish_thread([text], dry_run=False)
    print(f"post_ids={result.post_ids}")
    print(f"partial={result.partial}")
    print(f"warnings={result.warnings}")
    if not result.post_ids:
        raise RuntimeError("publish failed: no post_ids")
    return result.post_ids


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--which", choices=sorted(POSTS), required=True)
    p.add_argument("--force", action="store_true", help="ignore TARGET_DATE check")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    today = datetime.now(JST).date().isoformat()
    if not args.force and today != TARGET_DATE:
        print(f"skip: today={today} target={TARGET_DATE}")
        return 0

    value_id, text = POSTS[args.which]
    print(f"value_id={value_id}")
    print("=== TEXT ===")
    print(text)

    if args.dry_run:
        print("dry-run: not publishing")
        return 0

    post_ids = asyncio.run(publish(text))

    # 台帳に雑談として記録（再利用キューには載せない）
    try:
        import json
        from pathlib import Path

        import config
        from picker import load_ledger, save_ledger

        entries = load_ledger()
        entries.append(
            {
                "item_code": f"value:{value_id}",
                "item_name": text[:40],
                "kind": "chitchat",
                "slot": 99,
                "posted_on": today,
                "threads_post_ids": post_ids,
                "reused": False,
            }
        )
        save_ledger(entries)
        print(f"ledger updated: {config.LEDGER_PATH}")
    except Exception as exc:
        print(f"WARNING: ledger update failed: {exc}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
