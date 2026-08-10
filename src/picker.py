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
# 紙類は ロール / 組 / 箱、長さは 30m などを許容
_SIZE_TOKEN_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:g|kg|ml|ｍl|ｌ|l|個|袋|本|パック|枚|ロール|組|箱|セット|巻|[mｍ])",
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
    """日付×商品枠の通し番号で悩みをローテ。

    TIMESAVE_ITEM_SLOTS は時短悩みだけを回す（通常枠のローテ長は変えない）。
    時短枠が空のときは all_pain_intents（時短専用含む）を通常ローテに混ぜる。
    """
    on = on or today_jst()
    day_i = on.toordinal()
    timesave_slots = tuple(getattr(config, "TIMESAVE_ITEM_SLOTS", ()) or ())
    if slot in timesave_slots:
        intents = config.timesave_pain_intents()
        if not intents:
            intents = config.PAIN_INTENTS
        k = timesave_slots.index(slot)
        idx = (day_i * max(1, len(timesave_slots)) + k) % len(intents)
        return intents[idx]

    # 時短専用枠が無いときは floor-wiper 等も通常ローテへ含める
    intents = (
        config.all_pain_intents()
        if not timesave_slots
        else config.PAIN_INTENTS
    )
    # 通常の商品枠だけを進める（時短枠は別カウンタ）
    regular_slots = tuple(s for s in config.ITEM_SLOTS if s not in timesave_slots)
    item_index = 0
    if slot in regular_slots:
        item_index = regular_slots.index(slot)
    elif slot in config.ITEM_SLOTS:
        item_index = config.ITEM_SLOTS.index(slot)
    idx = (day_i * max(1, len(regular_slots) or 1) + item_index) % len(intents)
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


def is_postage_included(item: RakutenItem) -> bool:
    """応答 postageFlag: 0=送料込 / 1=送料別（公式ドキュメント準拠）。"""
    return int(getattr(item, "postage_flag", 1) or 0) == 0


def passes_quality(item: RakutenItem, *, max_price: Optional[int] = None) -> bool:
    price_limit = int(max_price) if max_price is not None else int(config.MAX_ITEM_PRICE)
    ok = (
        item.review_average >= config.MIN_REVIEW_AVERAGE
        and item.review_count >= config.MIN_REVIEW_COUNT
        and bool(item.affiliate_url)
        and item.item_price > 0
        and item.item_price <= price_limit
        and not is_blocked(item)
    )
    if not ok:
        return False
    if getattr(config, "REQUIRE_POSTAGE_INCLUDED", False) and not is_postage_included(item):
        return False
    return True


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


def _sort_candidates(items: List[RakutenItem]) -> List[RakutenItem]:
    """送料込 → レビュー件数 → 評価 → 安い順。"""
    prefer = bool(getattr(config, "PREFER_POSTAGE_INCLUDED", True))

    def key(i: RakutenItem) -> tuple:
        postage_rank = 0 if (not prefer or is_postage_included(i)) else 1
        return (
            postage_rank,
            -int(i.review_count or 0),
            -float(i.review_average or 0),
            int(i.item_price or 0),
        )

    return sorted(items, key=key)


def _filter_candidates(
    items: List[RakutenItem],
    *,
    used: Set[str],
    pain: Optional[config.PainIntent] = None,
    band: Optional[tuple[int, int]] = None,
    require_pain_match: bool = True,
) -> List[RakutenItem]:
    """品質・価格・ブロックを満たす候補。pain があるときは name_hints 一致を必須にする。"""
    price_cap = getattr(pain, "max_price", None) if pain is not None else None
    quality = [
        i
        for i in items
        if i.item_code not in used and passes_quality(i, max_price=price_cap)
    ]
    if pain is not None and require_pain_match:
        quality = [i for i in quality if _matches_pain(i, pain)]
    if band:
        banded = [i for i in quality if _in_band(i, band)]
        if banded:
            quality = banded
    if not quality:
        return []
    # 送料込を優先。候補が両方あるときは送料込だけに絞る（敬遠されやすい送料別を避ける）
    if getattr(config, "PREFER_POSTAGE_INCLUDED", True) and not getattr(
        config, "REQUIRE_POSTAGE_INCLUDED", False
    ):
        included = [i for i in quality if is_postage_included(i)]
        if included:
            quality = included
    return _sort_candidates(quality)


def _search_pain_items(
    client: RakutenClient,
    pain: config.PainIntent,
    *,
    genre_id: Optional[str],
    postage_flag: Optional[int] = None,
) -> List[RakutenItem]:
    price_cap = pain.max_price if pain.max_price is not None else int(config.MAX_ITEM_PRICE)
    return client.search_items(
        pain.keyword,
        hits=config.RANKING_HITS,
        sort="-reviewCount",
        genre_id=genre_id,
        max_price=int(price_cap),
        pages=3,
        postage_flag=postage_flag,
    )


def _candidates_for_pain(
    client: RakutenClient,
    pain: config.PainIntent,
    *,
    used: Set[str],
    band: tuple[int, int],
) -> List[RakutenItem]:
    """1つの悩みについて検索→ジャンルランキングの順で厳格マッチ候補を返す。

    送料込を先に取り、取れなければ送料条件なしで再検索する。
    """
    prefer = bool(getattr(config, "PREFER_POSTAGE_INCLUDED", True))
    require = bool(getattr(config, "REQUIRE_POSTAGE_INCLUDED", False))
    # リクエスト postageFlag=1 → 送料込/送料無料のみ
    postage_attempts: List[Optional[int]] = [1, None] if prefer else [None]
    if require:
        postage_attempts = [1]

    # ジャンル指定 → ジャンルなし、の順。maxPrice 付きで高レビュー商品を拾う。
    for postage_flag in postage_attempts:
        for genre_id in (pain.genre_id, None):
            try:
                searched = _search_pain_items(
                    client, pain, genre_id=genre_id, postage_flag=postage_flag
                )
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
    all_pains = list(config.all_pain_intents())
    if pain_id:
        primary_pain = next((p for p in all_pains if p.id == pain_id), None)
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
    # 時短枠は時短悩みだけに閉じる（柔軟剤など通常枠へ落とさない）
    timesave_slots = tuple(getattr(config, "TIMESAVE_ITEM_SLOTS", ()) or ())
    pool = (
        list(config.timesave_pain_intents())
        if slot in timesave_slots
        else list(all_pains)
    )
    pains: List[config.PainIntent] = []
    if primary_pain is not None:
        pains.append(primary_pain)
        for p in pool:
            if p.id != primary_pain.id:
                pains.append(p)
    else:
        pains = list(pool)

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
            "kind": _value_kind(value_id),
            "slot": slot,
            "posted_on": posted_on,
            "threads_post_ids": threads_post_ids,
            "reused": reused,
        }
    )
    save_ledger(entries, ledger_path)
    # 雑談・アンケートは一度きり。再利用キューに載せない。
    if _is_oneshot(value_id):
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


def _value_kind(value_id: str) -> str:
    if value_id.startswith("ogiri-"):
        return "ogiri"
    try:
        from value_posts import is_ask_chitchat_id, is_chitchat_id

        if is_ask_chitchat_id(value_id):
            return "ask-chitchat"
        if is_chitchat_id(value_id):
            return "chitchat"
    except Exception:
        pass
    return "value"


def _is_oneshot(value_id: str) -> bool:
    try:
        from value_posts import is_oneshot_value_id

        return is_oneshot_value_id(value_id)
    except Exception:
        return value_id.startswith(("ask-", "chat-auto-", "chat-summer-", "ogiri-"))


def _is_chitchat(value_id: str) -> bool:
    try:
        from value_posts import is_chitchat_id

        return is_chitchat_id(value_id)
    except Exception:
        return False
