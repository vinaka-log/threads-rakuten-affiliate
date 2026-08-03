"""Publish ask-style engagement chitchat (ice-cream hit pattern).

Daily extras at 11:00 / 16:00 JST via workflow. Mixes seasonal hooks with
light trend/news seeds. No affiliate / no product pitch.

Usage:
  python scripts/publish_ask_chitchat.py --slot 1
  python scripts/publish_ask_chitchat.py --slot 2 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

import config
from ask_chitchat import ensure_ask_supply, pick_ask_post
from picker import load_ledger, save_ledger
from threads_client import ThreadsClient

JST = timezone(timedelta(hours=9))


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
    p.add_argument(
        "--slot",
        type=int,
        choices=(1, 2),
        required=True,
        help="1=11:00 JST, 2=16:00 JST (salt for pool pick)",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    today = datetime.now(JST).date().isoformat()
    ensure_ask_supply(refresh_trends=True)
    picked = pick_ask_post(slot_salt=args.slot)
    value_id = str(picked.get("id") or "")
    text = str(picked.get("text") or "").strip()
    if not value_id or not text:
        raise RuntimeError("picked ask post is empty")

    print(f"value_id={value_id}")
    print(f"source={picked.get('source')}")
    print("=== TEXT ===")
    print(text)

    if args.dry_run:
        print("dry-run: not publishing")
        return 0

    post_ids = asyncio.run(publish(text))

    try:
        entries = load_ledger()
        entries.append(
            {
                "item_code": f"value:{value_id}",
                "item_name": text[:40],
                "kind": "ask-chitchat",
                "slot": 90 + int(args.slot),
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
