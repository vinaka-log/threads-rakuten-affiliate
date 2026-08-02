"""ジャンルローテ + 悩みキーワード起点 + posted.json 台帳による商品ピッカー。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Set

import config
from rakuten import RakutenClient, RakutenItem

JST = timezone(timedelta(hours=9))

# 消耗品らしい容量・個数表記（収納グッズを落とす）
_SIZE_TOKEN_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:g|kg|ml|ｍl|ｌ|l|個|袋|本|パック|枚)",
    re.IGNORECASE,
)


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


def is_blocked(item: RakutenItem) -> bool:
    """ペルソナ外（美容・ガジェット・詰め替えボトル等）を商品名で弾く。"""
    name = item.item_name.lower()
    return any(h.lower() in name for h in config.BLOCK_NAME_HINTS)


def passes_quality(item: RakutenItem) -> bool:
    return (
        item.review_average >= config.MIN_REVIEW_AVERAGE
        and item.review_count >= config.MIN_REVIEW_COUNT
        and bool(item.affiliate_url)
        and item.item_price > 0
        and item.item_price <= int(config.MAX_ITEM_PRICE)
        and not is_blocked(item)
    )


def _name_matches(item: RakutenItem, hints: tuple[str, ...]) -> bool:
    if not hints:
        return False
    name = item.item_name.lower()
    return any(h.lower() in name for h in hints)


def _matches_pain(item: RakutenItem, pain: config.PainIntent) -> bool:
    """悩みの name_hints / require / exclude / 容量表記をすべて満たすか。"""
    name = item.item_name
    if not _name_matches(item, pain.name_hints):
        return False
    require = tuple(pain.require_name_hints or ())
    if require and not _name_matches(item, require):
        return False
    exclude = tuple(pain.exclude_name_hints or ())
    if exclude and any(h.lower() in name.lower() for h in exclude):
        return False
    if pain.require_size_token and not _SIZE_TOKEN_RE.search(name):
        return False
    return True


def _filter_candidates(
    items: List[RakutenItem],
    *,
    used: Set[str],
    pain: Optional[config.PainIntent] = None,
    band: Optional[tuple[int, int]] = None,
    require_pain_match: bool = True,
) -> List[RakutenItem]:
    """品質・価格・ブロックを満たす候補。pain があるときは name_hints 一致を必須にする。"""
    quality = [i for i in items if i.item_code not in used and passes_quality(i)]
    if pain is not None and require_pain_match:
        quality = [i for i in quality if _matches_pain(i, pain)]
    if band:
        banded = [i for i in quality if _in_band(i, band)]
        if banded:
            return banded
    return quality


def _search_pain_items(
    client: RakutenClient,
    pain: config.PainIntent,
    *,
    genre_id: Optional[str],
) -> List[RakutenItem]:
    return client.search_items(
        pain.keyword,
        hits=config.RANKING_HITS,
        sort="-reviewCount",
        genre_id=genre_id,
        max_price=int(config.MAX_ITEM_PRICE),
        pages=3,
    )


def _candidates_for_pain(
    client: RakutenClient,
    pain: config.PainIntent,
    *,
    used: Set[str],
    band: tuple[int, int],
) -> List[RakutenItem]:
    """1つの悩みについて検索→ジャンルランキングの順で厳格マッチ候補を返す。"""
    # ジャンル指定 → ジャンルなし、の順。maxPrice 付きで高レビュー商品を拾う。
    for genre_id in (pain.genre_id, None):
        try:
            searched = _search_pain_items(client, pain, genre_id=genre_id)
            found = _filter_candidates(searched, used=used, pain=pain)
            if found:
                return found
        except Exception:
            continue

    genre = genre_by_id(pain.genre_id)
    assert genre is not None
    try:
        ranking = client.fetch_ranking(genre.id, hits=config.RANKING_HITS)
    except Exception:
        return []
    return _filter_candidates(ranking, used=used, pain=pain, band=band)


def pick_item(
    client: RakutenClient,
    *,
    slot: int = 0,
    genre_id: Optional[str] = None,
    on: Optional[date] = None,
    pain_id: Optional[str] = None,
    ledger_path: Path = config.LEDGER_PATH,
) -> PickResult:
    """悩みキーワード起点で商品を1件選ぶ。

    悩みが決まったら name_hints 不一致の商品は絶対に選ばない。
    主悩みで取れなければ他の悩みへローテし、それでも無ければ失敗する
    （無関係商品のフォールバックはしない）。
    """
    on = on or today_jst()
    primary_pain: Optional[config.PainIntent] = None
    if pain_id:
        primary_pain = next((p for p in config.PAIN_INTENTS if p.id == pain_id), None)
        if primary_pain is None:
            raise ValueError(f"未知の pain_id: {pain_id}")
    elif genre_id is None:
        primary_pain = pain_for_slot(slot, on)

    entries = load_ledger(ledger_path)
    used = recent_item_codes(entries, on=on)
    band = rank_band_for(on)

    # 明示 genre のみ（悩みなし）: 品質・価格・ブロックだけ
    if primary_pain is None and genre_id:
        genre = genre_by_id(genre_id)
        assert genre is not None
        ranking = client.fetch_ranking(genre.id, hits=config.RANKING_HITS)
        candidates = _filter_candidates(ranking, used=used, pain=None, band=band)
        if not candidates:
            raise RuntimeError(
                f"投稿可能な商品がありません genre={genre.id}({genre.label}) "
                f"pain=- used={len(used)} max_price={config.MAX_ITEM_PRICE}"
            )
        return PickResult(
            item=candidates[0],
            genre=genre,
            slot=slot,
            posted_on=on.isoformat(),
            pain=None,
        )

    # 悩みローテ: 主悩み → 残り（順序を保ったまま一周）
    pains: List[config.PainIntent] = []
    if primary_pain is not None:
        pains.append(primary_pain)
        for p in config.PAIN_INTENTS:
            if p.id != primary_pain.id:
                pains.append(p)
    else:
        pains = list(config.PAIN_INTENTS)

    last_genre = genre_for_slot(slot, on)
    for pain in pains:
        genre = genre_by_id(pain.genre_id)
        assert genre is not None
        last_genre = genre
        candidates = _candidates_for_pain(client, pain, used=used, band=band)
        if candidates:
            return PickResult(
                item=candidates[0],
                genre=genre,
                slot=slot,
                posted_on=on.isoformat(),
                pain=pain,
            )

    raise RuntimeError(
        f"投稿可能な商品がありません genre={last_genre.id}({last_genre.label}) "
        f"pain={primary_pain.id if primary_pain else '-'} used={len(used)} "
        f"max_price={config.MAX_ITEM_PRICE}（悩み不一致・高額・低評価のフォールバックは禁止）"
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
            "kind": "chitchat" if _is_chitchat(value_id) else "value",
            "slot": slot,
            "posted_on": posted_on,
            "threads_post_ids": threads_post_ids,
            "reused": reused,
        }
    )
    save_ledger(entries, ledger_path)
    # 雑談は一度きり。再利用キューに載せない。
    if _is_chitchat(value_id):
        return
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


def _is_chitchat(value_id: str) -> bool:
    try:
        from value_posts import is_chitchat_id

        return is_chitchat_id(value_id)
    except Exception:
        return False
