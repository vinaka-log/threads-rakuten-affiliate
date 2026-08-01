"""ジャンルローテ + posted.json 台帳による商品ピッカー。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Set

import config
from rakuten import RakutenClient, RakutenItem

JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class PickResult:
    item: RakutenItem
    genre: config.Genre
    slot: int
    posted_on: str  # YYYY-MM-DD (JST)


def today_jst() -> date:
    return datetime.now(JST).date()


def load_ledger(path: Path = config.LEDGER_PATH) -> List[dict]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        entries = raw.get("entries") or []
    elif isinstance(raw, list):
        entries = raw
    else:
        entries = []
    return [e for e in entries if isinstance(e, dict)]


def save_ledger(entries: List[dict], path: Path = config.LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 古いエントリも残すが、表示用に新しい順
    cleaned = sorted(
        entries,
        key=lambda e: str(e.get("posted_on") or ""),
        reverse=True,
    )
    payload = {
        "updated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "entries": cleaned,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def recent_item_codes(entries: List[dict], *, days: int = config.DEDUP_DAYS, on: Optional[date] = None) -> Set[str]:
    on = on or today_jst()
    cutoff = on - timedelta(days=days)
    codes: Set[str] = set()
    for e in entries:
        code = str(e.get("item_code") or "").strip()
        posted = str(e.get("posted_on") or "").strip()
        if not code or not posted:
            continue
        try:
            d = date.fromisoformat(posted)
        except ValueError:
            continue
        if d >= cutoff:
            codes.add(code)
    return codes


def genre_for_slot(slot: int, on: Optional[date] = None) -> config.Genre:
    """日付×slot でジャンルをローテ。"""
    on = on or today_jst()
    if not (0 <= slot < config.POSTS_PER_DAY):
        raise ValueError(f"slot は 0..{config.POSTS_PER_DAY - 1} です: {slot}")
    genres = config.GENRES
    index = (on.toordinal() * config.POSTS_PER_DAY + slot) % len(genres)
    return genres[index]


def genre_by_id(genre_id: str) -> Optional[config.Genre]:
    for g in config.GENRES:
        if g.id == genre_id:
            return g
    return config.Genre(id=genre_id, label=f"genre:{genre_id}", short="売れ筋")


def rank_band_for(on: Optional[date] = None) -> tuple[int, int]:
    """日替わりでrank帯をローテ（上位帯は競合と被るため準上位帯も使う）。"""
    on = on or today_jst()
    bands = config.RANK_BANDS
    return bands[on.toordinal() % len(bands)]


def _in_band(item: RakutenItem, band: tuple[int, int]) -> bool:
    if item.rank is None:
        return True
    return band[0] <= item.rank <= band[1]


def passes_quality(item: RakutenItem) -> bool:
    return (
        item.review_average >= config.MIN_REVIEW_AVERAGE
        and item.review_count >= config.MIN_REVIEW_COUNT
        and bool(item.affiliate_url)
        and item.item_price > 0
    )


def pick_item(
    client: RakutenClient,
    *,
    slot: int = 0,
    genre_id: Optional[str] = None,
    on: Optional[date] = None,
    ledger_path: Path = config.LEDGER_PATH,
) -> PickResult:
    """ランキング上位から未投稿・品質OKの商品を1件選ぶ。"""
    on = on or today_jst()
    if genre_id:
        genre = genre_by_id(genre_id)
        assert genre is not None
    else:
        genre = genre_for_slot(slot, on)

    entries = load_ledger(ledger_path)
    used = recent_item_codes(entries, on=on)
    ranking = client.fetch_ranking(genre.id, hits=config.RANKING_HITS)

    band = rank_band_for(on)
    quality = [i for i in ranking if i.item_code not in used and passes_quality(i)]
    # まず当日のrank帯から選び、無ければ帯を無視して品質OKから選ぶ
    candidates = [i for i in quality if _in_band(i, band)] or quality
    if not candidates:
        # 品質フィルタを緩めて再試行（レビュー件数のみ半分）
        soft = [
            i
            for i in ranking
            if i.item_code not in used
            and i.review_average >= config.MIN_REVIEW_AVERAGE
            and i.review_count >= max(20, config.MIN_REVIEW_COUNT // 2)
            and i.affiliate_url
        ]
        candidates = soft
    if not candidates:
        # それでも無ければ未使用の先頭（品質不問・URL必須）
        candidates = [i for i in ranking if i.item_code not in used and i.affiliate_url]
    if not candidates:
        raise RuntimeError(
            f"投稿可能な商品がありません genre={genre.id}({genre.label}) "
            f"used={len(used)} ranking={len(ranking)}"
        )

    item = candidates[0]
    return PickResult(
        item=item,
        genre=genre,
        slot=slot,
        posted_on=on.isoformat(),
    )


def record_post(
    pick: PickResult,
    *,
    threads_post_ids: List[str],
    dry_run: bool = False,
    ledger_path: Path = config.LEDGER_PATH,
) -> None:
    """台帳に追記。dry_run では書かない。"""
    if dry_run:
        return
    entries = load_ledger(ledger_path)
    entries.append(
        {
            "item_code": pick.item.item_code,
            "item_name": pick.item.item_name,
            "genre_id": pick.genre.id,
            "genre_label": pick.genre.label,
            "slot": pick.slot,
            "posted_on": pick.posted_on,
            "threads_post_ids": threads_post_ids,
            "affiliate_url": pick.item.affiliate_url,
            "rank": pick.item.rank,
        }
    )
    save_ledger(entries, ledger_path)


def record_value_post(
    *,
    value_id: str,
    slot: int,
    posted_on: str,
    threads_post_ids: List[str],
    dry_run: bool = False,
    reused: bool = False,
    ledger_path: Path = config.LEDGER_PATH,
) -> None:
    """価値投稿を台帳に追記。dry_run では書かない。再利用キューにも登録。"""
    if dry_run:
        return
    entries = load_ledger(ledger_path)
    entries.append(
        {
            "item_code": f"value:{value_id}",
            "item_name": f"価値投稿 {value_id}",
            "kind": "value",
            "slot": slot,
            "posted_on": posted_on,
            "threads_post_ids": threads_post_ids,
            "reused": reused,
        }
    )
    save_ledger(entries, ledger_path)
    try:
        from reuse import register_value_post

        register_value_post(
            value_id=value_id,
            posted_on=posted_on,
            threads_post_ids=threads_post_ids,
            source="reuse" if reused else "auto",
        )
    except Exception:
        # キュー更新失敗で投稿自体は落とさない
        pass
