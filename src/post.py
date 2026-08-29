#!/usr/bin/env python3
"""Threads × 楽天アフィリエイト 自動投稿 CLI。

例:
  PYTHONPATH=src:. python src/post.py --dry-run --slot 0
  PYTHONPATH=src:. python src/post.py --publish --slot 1
  PYTHONPATH=src:. python src/post.py --dry-run --genre 100533
  PYTHONPATH=src:. python src/post.py --list-genres
  PYTHONPATH=src:. python src/post.py --list-reuse
  PYTHONPATH=src:. python src/post.py --mark-reuse stock-buy
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import replace
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
from composer import compose, compose_digest, compose_ogiri, compose_value
from picker import genre_for_slot, pick_item, record_post, record_value_post, today_jst
from rakuten import RakutenClient
from reuse import (
    apply_insights,
    backfill_from_ledger,
    load_reuse,
    mark_winner,
    pick_reuse_value,
)
from threads_client import ThreadsApiError, ThreadsClient


def _default_slot() -> int:
    raw = (os.environ.get("THREADS_SLOT") or "").strip()
    if raw.isdigit():
        return int(raw)
    # 現在時刻（JST）に最も近い枠を選ぶ
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone(timedelta(hours=9)))
    minutes = now.hour * 60 + now.minute
    best, best_dist = 0, 10**9
    for i, label in enumerate(config.SLOT_LABELS):
        h, m = label.split(":")
        dist = abs(minutes - (int(h) * 60 + int(m)))
        if dist < best_dist:
            best, best_dist = i, dist
    return best


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
        help="日内枠 0..9（時刻は config.SLOT_LABELS 参照）",
    )
    p.add_argument(
        "--genre",
        type=str,
        default=None,
        help="楽天 genreId を直接指定（省略時は悩み/日付ローテ）",
    )
    p.add_argument(
        "--pain",
        type=str,
        default=None,
        help="悩みIDを直接指定（config.PAIN_INTENTS の id）",
    )
    p.add_argument(
        "--no-image",
        action="store_true",
        help="商品画像を付けない（既定は付けない。ATTACH_ITEM_IMAGE で変更可）",
    )
    p.add_argument(
        "--date",
        type=str,
        default=None,
        help="基準日 YYYY-MM-DD（ローテ検証用・既定は今日JST）",
    )
    p.add_argument("--list-genres", action="store_true", help="設定ジャンル一覧")
    p.add_argument("--list-reuse", action="store_true", help="再利用キュー一覧")
    p.add_argument(
        "--mark-reuse",
        type=str,
        default=None,
        metavar="VALUE_ID",
        help="伸びた価値投稿を再利用キューに高優先で登録",
    )
    p.add_argument(
        "--backfill-reuse",
        action="store_true",
        help="台帳の価値投稿を再利用キューへ取り込む",
    )
    p.add_argument(
        "--sync-insights",
        action="store_true",
        help="Threads Insights で views/likes を取得し再利用優先度を更新",
    )
    p.add_argument(
        "--template",
        type=str,
        default=None,
        help="投稿テンプレID（hook-benefit / hook-stock / hook-heavy / hook-tonight / hook-reason）",
    )
    kind = p.add_mutually_exclusive_group()
    kind.add_argument(
        "--value",
        action="store_true",
        help="静的価値投稿（リンクなし）を強制。省略時は slot 種別で自動判定",
    )
    kind.add_argument(
        "--digest",
        action="store_true",
        help="ランキングダイジェスト（リンクなし）を強制",
    )
    kind.add_argument(
        "--item",
        action="store_true",
        help="商品紹介投稿を強制",
    )
    kind.add_argument(
        "--ogiri",
        action="store_true",
        help="ジブリ大喜利（画像＋短文）を強制",
    )
    kind.add_argument(
        "--reuse",
        action="store_true",
        help="再利用キューから価値投稿を強制",
    )
    p.add_argument(
        "--value-id",
        type=str,
        default=None,
        help="価値投稿のIDを直接指定（省略時は日付ローテ）",
    )
    p.add_argument(
        "--digest-format",
        type=str,
        choices=("top3", "quiz", "sleeper"),
        default=None,
        help="ダイジェスト形式を直接指定（省略時は日付×枠でローテ）",
    )
    return p


def _print_preview(pick, composed, *, dry_run: bool, image_url: str = "") -> None:
    label = config.SLOT_LABELS[pick.slot] if 0 <= pick.slot < len(config.SLOT_LABELS) else "?"
    print("=== Threads × Rakuten preview ===")
    print(f"mode: {'dry-run' if dry_run else 'publish'}")
    print(f"date: {pick.posted_on}  slot: {pick.slot} ({label})")
    print(f"genre: {pick.genre.id} / {pick.genre.label}")
    if pick.pain:
        print(f"pain: {pick.pain.id} / {pick.pain.pain}")
    print(f"item: {pick.item.item_code}")
    print(f"name: {pick.item.item_name}")
    print(
        f"price: {pick.item.item_price:,}  "
        f"review: {pick.item.review_average:.1f} ({pick.item.review_count:,})  "
        f"rank: {pick.item.rank}"
    )
    if image_url:
        print(f"image: {image_url}")
    print(f"template: {composed.template_id}")
    print("---")
    for i, text in enumerate(composed.texts):
        title = "MAIN" if i == 0 else f"REPLY[{i}]"
        print(f"[{title}] ({len(text)} chars)")
        print(text)
        print("---")


async def _publish(texts, *, image_url: str | None = None, poll_options=None):
    client = ThreadsClient(
        access_token=os.environ.get("THREADS_ACCESS_TOKEN", ""),
        user_id=os.environ.get("THREADS_USER_ID", ""),
    )
    return await client.publish_thread(
        texts,
        image_url=image_url,
        poll_options=poll_options,
        dry_run=False,
    )


async def _sync_insights() -> int:
    client = ThreadsClient(
        access_token=os.environ.get("THREADS_ACCESS_TOKEN", ""),
        user_id=os.environ.get("THREADS_USER_ID", ""),
    )
    metrics: dict[str, dict[str, int]] = {}
    for c in load_reuse():
        if not c.threads_post_id:
            continue
        try:
            metrics[c.threads_post_id] = await client.fetch_media_insights(c.threads_post_id)
            print(
                f"insights {c.value_id} ({c.threads_post_id}): "
                f"{metrics[c.threads_post_id]}"
            )
        except ThreadsApiError as exc:
            print(f"insights skip {c.value_id}: {exc}", file=sys.stderr)
    return apply_insights(metrics)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_genres:
        for g in config.GENRES:
            print(f"{g.id}\t{g.short}\t{g.label}")
        print("--- pains ---")
        for p in config.all_pain_intents():
            tag = "timesave" if p.timesave else "regular"
            print(f"{p.id}\t{p.genre_id}\t{tag}\t{p.keyword}\t{p.pain}")
        return 0

    if args.list_reuse:
        on = today_jst()
        for c in load_reuse():
            due = "due" if (on - date.fromisoformat(c.last_posted_on)).days >= config.REUSE_INTERVAL_DAYS else "wait"
            print(
                f"{c.value_id}\tlast={c.last_posted_on}\t"
                f"prio={c.priority}\tviews={c.views}\tlikes={c.likes}\t"
                f"reuse_count={c.reuse_count}\t{due}\tsource={c.source}"
            )
        return 0

    if args.mark_reuse:
        c = mark_winner(args.mark_reuse)
        print(f"marked reuse winner: {c.value_id} priority={c.priority} last={c.last_posted_on}")
        return 0

    if args.backfill_reuse:
        n = backfill_from_ledger()
        print(f"backfilled {n} value posts into reuse queue")
        return 0

    if args.sync_insights:
        n = asyncio.run(_sync_insights())
        print(f"updated insights on {n} candidates → {config.REUSE_PATH}")
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

    # 投稿種別の判定:
    #   明示フラグ > slot 種別の自動割当
    #   REUSE_SLOTS では期限到来の再利用を優先
    reuse_candidate = None
    ogiri_slots = tuple(getattr(config, "OGIRI_SLOTS", ()) or ())
    if args.reuse:
        kind = "reuse"
    elif args.value:
        kind = "value"
    elif args.digest:
        kind = "digest"
    elif getattr(args, "ogiri", False):
        kind = "ogiri"
    elif args.item or args.genre or args.template or args.pain:
        kind = "item"
    elif slot in ogiri_slots:
        kind = "ogiri"
    elif slot in config.VALUE_SLOTS:
        kind = "value"
        if slot in config.REUSE_SLOTS and not args.value_id:
            reuse_candidate = pick_reuse_value(on, slot=slot)
            if reuse_candidate is not None:
                kind = "reuse"
    elif slot in config.DIGEST_SLOTS:
        kind = "digest"
    else:
        kind = "item"

    if kind == "ogiri":
        composed = compose_ogiri(on, slot)
        label = config.SLOT_LABELS[slot] if 0 <= slot < len(config.SLOT_LABELS) else "?"
        print("=== Threads ogiri post preview ===")
        print(f"mode: {'dry-run' if dry_run else 'publish'}")
        print(f"date: {on.isoformat()}  slot: {slot} ({label})")
        print(f"template: {composed.template_id}")
        if composed.image_url:
            print(f"image: {composed.image_url}")
        print("---")
        for i, text in enumerate(composed.texts):
            title = "MAIN" if i == 0 else f"REPLY[{i}]"
            print(f"[{title}] ({len(text)} chars)")
            print(text)
            print("---")
        if dry_run:
            print("dry-run: not publishing, ledger unchanged")
            return 0
        result = asyncio.run(
            _publish(composed.texts, image_url=composed.image_url or None)
        )
        if result.warnings:
            for w in result.warnings:
                print(f"WARNING: {w}", file=sys.stderr)
        print(f"published post_ids={result.post_ids} partial={result.partial}")
        record_value_post(
            value_id=composed.item_code.split(":", 1)[-1],
            slot=slot,
            posted_on=on.isoformat(),
            threads_post_ids=result.post_ids,
            dry_run=False,
            reused=False,
        )
        print(f"ledger updated: {config.LEDGER_PATH}")
        return 0

    if kind in ("value", "digest", "reuse"):
        reused = False
        if kind == "reuse":
            reuse_candidate = reuse_candidate or pick_reuse_value(on, slot=slot)
            if reuse_candidate is None:
                print("reuse queue has no due candidate; falling back to value rotation")
                kind = "value"
            else:
                composed = compose_value(on, slot, value_id=reuse_candidate.value_id)
                composed = replace(
                    composed,
                    template_id=f"value-reuse:{reuse_candidate.value_id}",
                )
                reused = True
        if kind == "value":
            composed = compose_value(on, slot, value_id=args.value_id)
        elif kind == "digest":
            composed = compose_digest(RakutenClient(), on, slot, fmt=args.digest_format)

        label = config.SLOT_LABELS[slot] if 0 <= slot < len(config.SLOT_LABELS) else "?"
        print(f"=== Threads {kind} post preview ===")
        print(f"mode: {'dry-run' if dry_run else 'publish'}")
        print(f"date: {on.isoformat()}  slot: {slot} ({label})")
        print(f"template: {composed.template_id}")
        if reused and reuse_candidate is not None:
            print(
                f"reuse: yes  last={reuse_candidate.last_posted_on}  "
                f"prio={reuse_candidate.priority} views={reuse_candidate.views}"
            )
        print("---")
        for i, text in enumerate(composed.texts):
            title = "MAIN" if i == 0 else f"REPLY[{i}]"
            print(f"[{title}] ({len(text)} chars)")
            print(text)
            print("---")
        if getattr(composed, "poll_options", None):
            print(f"[POLL] {composed.poll_options}")
            print("---")
        if dry_run:
            print("dry-run: not publishing, ledger unchanged")
            return 0
        result = asyncio.run(
            _publish(composed.texts, poll_options=getattr(composed, "poll_options", None) or None)
        )
        if result.warnings:
            for w in result.warnings:
                print(f"WARNING: {w}", file=sys.stderr)
        print(f"published post_ids={result.post_ids} partial={result.partial}")
        record_value_post(
            value_id=composed.item_code.split(":", 1)[-1],
            slot=slot,
            posted_on=on.isoformat(),
            threads_post_ids=result.post_ids,
            dry_run=False,
            reused=reused,
        )
        print(f"ledger updated: {config.LEDGER_PATH}")
        return 0

    from picker import pain_for_slot

    pain_preview = args.pain or (pain_for_slot(slot, on).id if slot in config.ITEM_SLOTS else "-")
    genre_preview = args.genre or (
        next((p.genre_id for p in config.all_pain_intents() if p.id == args.pain), None)
        if args.pain
        else None
    ) or genre_for_slot(slot, on).id
    print(
        f"resolving item for slot={slot} genre={genre_preview} "
        f"pain={pain_preview} date={on.isoformat()}"
    )

    rakuten = RakutenClient()
    pick = pick_item(
        rakuten,
        slot=slot,
        genre_id=args.genre,
        pain_id=args.pain,
        on=on,
    )
    composed = compose(pick, template_id=args.template)
    image_url = ""
    if config.ATTACH_ITEM_IMAGE and not args.no_image:
        image_url = pick.item.image_url or ""
    _print_preview(pick, composed, dry_run=dry_run, image_url=image_url)

    if dry_run:
        print("dry-run: not publishing, ledger unchanged")
        return 0

    result = asyncio.run(_publish(composed.texts, image_url=image_url or None))
    if result.warnings:
        for w in result.warnings:
            print(f"WARNING: {w}", file=sys.stderr)
    print(f"published post_ids={result.post_ids} partial={result.partial}")
    record_post(pick, threads_post_ids=result.post_ids, dry_run=False)
    print(f"ledger updated: {config.LEDGER_PATH}")
    return 0 if not result.partial else 0  # 部分成功もジョブ成功扱い


if __name__ == "__main__":
    raise SystemExit(main())
