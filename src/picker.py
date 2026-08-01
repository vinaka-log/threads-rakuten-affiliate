"""ジャンルローテ + 悩みキーワード起点 + posted.json 台帳による商品ピッカー。"""

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
    pain: Optional[config.PainIntent] = None


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
    # 悩み起点で GENRES 外（例: 水=100227）を使う場合
    shorts = {
        "100227": "ドリンク",
        "100939": "日用品",
        "551167": "キッチン",
    }
    return config.Genre(
        id=genre_id,
        label=f"genre:{genre_id}",
        short=shorts.get(genre_id, "日用品"),
    )


def pain_for_slot(slot: int, on: Optional[date] = None) -> config.PainIntent:
    """日付×商品枠の通し番号で悩みをローテ。"""
    on = on or today_jst()
    intents = config.PAIN_INTENTS
    # 商品枠だけを進める（価値/ダイジェスト枠では使わない想定）
    item_index = 0
    if slot in config.ITEM_SLOTS:
        item_index = config.ITEM_SLOTS.index(slot)
    day_i = on.toordinal()
    idx = (day_i * max(1, len(config.ITEM_SLOTS)) + item_index) % len(intents)
    return intents[idx]


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


def _name_matches(item: RakutenItem, hints: tuple[str, ...]) -> bool:
    name = item.item_name.lower()
    return any(h.lower() in name for h in hints)


def _filter_candidates(
    items: List[RakutenItem],
    *,
    used: Set[str],
    pain: Optional[config.PainIntent] = None,
    band: Optional[tuple[int, int]] = None,
) -> List[RakutenItem]:
    quality = [i for i in items if i.item_code not in used and passes_quality(i)]
    if pain:
        hinted = [i for i in quality if _name_matches(i, pain.name_hints)]
        quality = hinted or quality
    if band:
        banded = [i for i in quality if _in_band(i, band)]
        if banded:
            return banded
    return quality


def pick_item(
    client: RakutenClient,
    *,
    slot: int = 0,
    genre_id: Optional[str] = None,
    on: Optional[date] = None,
    pain_id: Optional[str] = None,
    ledger_path: Path = config.LEDGER_PATH,
) -> PickResult:
    """悩みキーワード起点で商品を1件選ぶ。取れなければランキングへフォールバック。"""
    on = on or today_jst()
    pain: Optional[config.PainIntent] = None
    if pain_id:
        pain = next((p for p in config.PAIN_INTENTS if p.id == pain_id), None)
        if pain is None:
            raise ValueError(f"未知の pain_id: {pain_id}")
    elif genre_id is None:
        pain = pain_for_slot(slot, on)

    if genre_id:
        genre = genre_by_id(genre_id)
        assert genre is not None
    elif pain is not None:
        genre = genre_by_id(pain.genre_id)
        assert genre is not None
    else:
        genre = genre_for_slot(slot, on)

    entries = load_ledger(ledger_path)
    used = recent_item_codes(entries, on=on)
    band = rank_band_for(on)

    candidates: List[RakutenItem] = []
    if pain is not None:
        try:
            searched = client.search_items(
                pain.keyword,
                hits=config.RANKING_HITS,
                sort="-reviewCount",
                genre_id=pain.genre_id,
            )
            candidates = _filter_candidates(searched, used=used, pain=pain)
        except Exception:
            candidates = []

    if not candidates:
        ranking = client.fetch_ranking(genre.id, hits=config.RANKING_HITS)
        candidates = _filter_candidates(ranking, used=used, pain=pain, band=band)
        if not candidates:
            soft = [
                i
                for i in ranking
                if i.item_code not in used
                and i.review_average >= config.MIN_REVIEW_AVERAGE
                and i.review_count >= max(20, config.MIN_REVIEW_COUNT // 2)
                and i.affiliate_url
            ]
            if pain:
                soft = [i for i in soft if _name_matches(i, pain.name_hints)] or soft
            candidates = soft
        if not candidates:
            candidates = [i for i in ranking if i.item_code not in used and i.affiliate_url]

    if not candidates:
        raise RuntimeError(
            f"投稿可能な商品がありません genre={genre.id}({genre.label}) "
            f"pain={pain.id if pain else '-'} used={len(used)}"
        )

    item = candidates[0]
    return PickResult(
        item=item,
        genre=genre,
        slot=slot,
        posted_on=on.isoformat(),
        pain=pain,
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
            "pain_id": pick.pain.id if pick.pain else "",
            "image_url": pick.item.image_url,
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
