"""商品データ → Threads 投稿文（テンプレート）。

制約（コードで強制）:
  - 本投稿に URL 禁止
  - リンクリプの1行目は必ず #PR
  - MAX_TEXT_LEN 以下
  - ハート系絵文字なし
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import List, Sequence, Tuple

import config
from picker import PickResult

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
_HEART_RE = re.compile(r"[💕❤️🧡💛💚💙💜🖤🤍🤎💖💗💓💞💘💝💟🫶♥]")


@dataclass(frozen=True)
class ComposedPost:
    texts: List[str]  # [本投稿, 自分リプ]
    item_code: str
    genre_id: str
    template_id: str


# 本投稿テンプレ: {short_name} {category} {rank} {review_avg} {review_count} {price}
_MAIN_TEMPLATES: Sequence[Tuple[str, str]] = (
    (
        "hook-rank",
        "で、楽天の{category}ランキング見てたら\n"
        "これレビュー{review_avg}点なのに毎日上位なんだけど\n\n"
        "「{short_name}」\n\n"
        "なんで売れてるのか分かった気がする\n"
        "続きはリプ👇",
    ),
    (
        "hook-review",
        "レビュー{review_count}件・平均{review_avg}点の{category}、\n"
        "いま楽天でよく見かけるやつ見つけた\n\n"
        "「{short_name}」\n\n"
        "口コミの共通点、気になる人いる？\n"
        "続きはリプ👇",
    ),
    (
        "hook-price",
        "これ{price}円でこのレビュー数は強すぎない？\n\n"
        "楽天{category}売れ筋の\n"
        "「{short_name}」\n\n"
        "とりあえず仕様だけ整理した↓\n"
        "続きはリプ👇",
    ),
    (
        "hook-daily",
        "今日の楽天{category}チェック結果\n\n"
        "ランキング上位で気になったのが\n"
        "「{short_name}」\n\n"
        "レビュー{review_avg}点 / {review_count}件\n"
        "詳細はリプにまとめた👇",
    ),
)

_REPLY_TEMPLATE = (
    "#PR\n"
    "アフィリエイトリンクを含みます\n\n"
    "【{short_name}】\n"
    "・価格: {price}円\n"
    "・レビュー: {review_avg}点（{review_count}件）\n"
    "{rank_line}"
    "・ショップ: {shop_name}\n\n"
    "気になった人はこちら↓\n"
    "{affiliate_url}"
)


def _fmt_price(n: int) -> str:
    return f"{n:,}"


def _pick_template_id(item_code: str, on: date, slot: int) -> str:
    seed = f"{item_code}:{on.isoformat()}:{slot}".encode()
    digest = hashlib.sha256(seed).hexdigest()
    idx = int(digest[:8], 16) % len(_MAIN_TEMPLATES)
    return _MAIN_TEMPLATES[idx][0]


def _truncate(text: str, limit: int = config.MAX_TEXT_LEN) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _validate(texts: List[str]) -> None:
    if len(texts) < 2:
        raise ValueError("本投稿とリプの2本が必要です")
    main, reply = texts[0], texts[1]
    if _URL_RE.search(main):
        raise ValueError("本投稿にURLを含められません")
    if not reply.lstrip().startswith("#PR"):
        raise ValueError("リンクリプの先頭は #PR である必要があります")
    for i, t in enumerate(texts):
        if _HEART_RE.search(t):
            raise ValueError(f"texts[{i}] にハート系絵文字があります")
        if len(t) > config.MAX_TEXT_LEN:
            raise ValueError(f"texts[{i}] が長すぎます ({len(t)} > {config.MAX_TEXT_LEN})")
        if not t.strip():
            raise ValueError(f"texts[{i}] が空です")


def compose(pick: PickResult, *, template_id: str | None = None) -> ComposedPost:
    item = pick.item
    on = date.fromisoformat(pick.posted_on)
    tid = template_id or _pick_template_id(item.item_code, on, pick.slot)
    templates = {k: v for k, v in _MAIN_TEMPLATES}
    if tid not in templates:
        raise ValueError(f"未知の template_id: {tid}")

    fields = {
        "short_name": item.short_name,
        "category": pick.genre.short,
        "rank": item.rank or "?",
        "review_avg": f"{item.review_average:.1f}",
        "review_count": f"{item.review_count:,}",
        "price": _fmt_price(item.item_price),
        "shop_name": item.shop_name or "楽天市場",
        "affiliate_url": item.affiliate_url,
        "rank_line": f"・ランキング: {item.rank}位付近\n" if item.rank else "",
    }

    main = _truncate(templates[tid].format(**fields))
    reply = _truncate(_REPLY_TEMPLATE.format(**fields))
    texts = [main, reply]
    _validate(texts)
    return ComposedPost(
        texts=texts,
        item_code=item.item_code,
        genre_id=pick.genre.id,
        template_id=tid,
    )
