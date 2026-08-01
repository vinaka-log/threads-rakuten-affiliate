#!/usr/bin/env python3
"""Threads × 楽天アフィリエイト 自動投稿 CLI。

例:
  PYTHONPATH=src:. python src/post.py --dry-run --slot 0
  PYTHONPATH=src:. python src/post.py --publish --slot 1
  PYTHONPATH=src:. python src/post.py --dry-run --genre 100939
  PYTHONPATH=src:. python src/post.py --list-genres
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import date
from pathlib import Path

# リポジトリルートを import パスに追加
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import config
from composer import compose, compose_value
from picker import genre_for_slot, pick_item, record_post, record_value_post, today_jst
from rakuten import RakutenClient
from threads_client import ThreadsClient


def _default_slot() -> int:
    raw = (os.environ.get("THREADS_SLOT") or "").strip()
    if raw.isdigit():
        return int(raw)
    # 時刻から推定（JST）
    hour = __import__("datetime").datetime.now(
        __import__("datetime").timezone(__import__("datetime").timedelta(hours=9))
    ).hour
    if hour < 10:
        return 0
    if hour < 16:
        return 1
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Threads × 楽天アフィリエイト自動投稿")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="投稿せず本文のみ表示")
    mode.add_argument("--publish", action="store_true", help="本番投稿")
    p.add_argument(
        "--slot",
        type=int,
        choices=tuple(range(config.POSTS_PER_DAY)),
        default=None,
        help="日内枠 0=08 1=12 2=20",
    )
    p.add_argument(
        "--genre",
        type=str,
        default=None,
        help="楽天 genreId を直接指定（省略時は日付×slot でローテ）",
    )
    p.add_argument(
        "--date",
        type=str,
        default=None,
        help="基準日 YYYY-MM-DD（ローテ検証用・既定は今日JST）",
    )
    p.add_argument("--list-genres", action="store_true", help="設定ジャンル一覧")
    p.add_argument(
        "--template",
        type=str,
        default=None,
        help="投稿テンプレID（hook-honne / hook-minna / hook-teiten / hook-price）",
    )
    kind = p.add_mutually_exclusive_group()
    kind.add_argument(
        "--value",
        action="store_true",
        help="価値投稿（リンクなし）を強制。省略時は slot が VALUE_SLOTS なら自動で価値投稿",
    )
    kind.add_argument(
        "--item",
        action="store_true",
        help="商品紹介投稿を強制（VALUE_SLOTS の slot でも商品を投稿）",
    )
    p.add_argument(
        "--value-id",
        type=str,
        default=None,
        help="価値投稿のIDを直接指定（省略時は日付ローテ）",
    )
    return p


def _print_preview(pick, composed, *, dry_run: bool) -> None:
    label = config.SLOT_LABELS[pick.slot] if 0 <= pick.slot < len(config.SLOT_LABELS) else "?"
    print("=== Threads × Rakuten preview ===")
    print(f"mode: {'dry-run' if dry_run else 'publish'}")
    print(f"date: {pick.posted_on}  slot: {pick.slot} ({label})")
    print(f"genre: {pick.genre.id} / {pick.genre.label}")
    print(f"item: {pick.item.item_code}")
    print(f"name: {pick.item.item_name}")
    print(
        f"price: {pick.item.item_price:,}  "
        f"review: {pick.item.review_average:.1f} ({pick.item.review_count:,})  "
        f"rank: {pick.item.rank}"
    )
    print(f"template: {composed.template_id}")
    print("---")
    for i, text in enumerate(composed.texts):
        title = "MAIN" if i == 0 else f"REPLY[{i}]"
        print(f"[{title}] ({len(text)} chars)")
        print(text)
        print("---")


async def _publish(texts):
    client = ThreadsClient(
        access_token=os.environ.get("THREADS_ACCESS_TOKEN", ""),
        user_id=os.environ.get("THREADS_USER_ID", ""),
    )
    return await client.publish_thread(texts, dry_run=False)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_genres:
        for g in config.GENRES:
            print(f"{g.id}\t{g.short}\t{g.label}")
        return 0

    dry_run = True
    if args.publish:
        dry_run = False
    elif args.dry_run:
        dry_run = True
    else:
        # 既定は dry-run（誤投稿防止）。CI では --publish を明示。
        dry_run = True

    on: date = today_jst()
    if args.date:
        on = date.fromisoformat(args.date)

    slot = args.slot if args.slot is not None else _default_slot()

    # 価値投稿かどうかの判定:
    #   --value 明示 > --item/--genre/--template による商品強制 > VALUE_SLOTS の自動割当
    is_value = args.value or (
        slot in config.VALUE_SLOTS
        and not args.item
        and not args.genre
        and not args.template
    )

    if is_value:
        composed = compose_value(on, slot, value_id=args.value_id)
        label = config.SLOT_LABELS[slot] if 0 <= slot < len(config.SLOT_LABELS) else "?"
        print("=== Threads value post preview ===")
        print(f"mode: {'dry-run' if dry_run else 'publish'}")
        print(f"date: {on.isoformat()}  slot: {slot} ({label})")
        print(f"template: {composed.template_id}")
        print("---")
        print(f"[MAIN] ({len(composed.texts[0])} chars)")
        print(composed.texts[0])
        print("---")
        if dry_run:
            print("dry-run: not publishing, ledger unchanged")
            return 0
        result = asyncio.run(_publish(composed.texts))
        if result.warnings:
            for w in result.warnings:
                print(f"WARNING: {w}", file=sys.stderr)
        print(f"published post_ids={result.post_ids} partial={result.partial}")
        record_value_post(
            value_id=composed.item_code.removeprefix("value:"),
            slot=slot,
            posted_on=on.isoformat(),
            threads_post_ids=result.post_ids,
            dry_run=False,
        )
        print(f"ledger updated: {config.LEDGER_PATH}")
        return 0

    genre_preview = args.genre or genre_for_slot(slot, on).id
    print(f"resolving item for slot={slot} genre={genre_preview} date={on.isoformat()}")

    rakuten = RakutenClient()
    pick = pick_item(rakuten, slot=slot, genre_id=args.genre, on=on)
    composed = compose(pick, template_id=args.template)
    _print_preview(pick, composed, dry_run=dry_run)

    if dry_run:
        print("dry-run: not publishing, ledger unchanged")
        return 0

    result = asyncio.run(_publish(composed.texts))
    if result.warnings:
        for w in result.warnings:
            print(f"WARNING: {w}", file=sys.stderr)
    print(f"published post_ids={result.post_ids} partial={result.partial}")
    record_post(pick, threads_post_ids=result.post_ids, dry_run=False)
    print(f"ledger updated: {config.LEDGER_PATH}")
    return 0 if not result.partial else 0  # 部分成功もジョブ成功扱い


if __name__ == "__main__":
    raise SystemExit(main())
