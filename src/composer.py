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
from sale import sale_lines
from value_posts import ValuePost, pick_value_post

_URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
# 注意: ❤️ 等の異体字セレクタ(U+FE0F)を文字クラスに含めると
# 🐻‍❄️ のような合成絵文字まで誤検知するため、基底文字のみ列挙する。
_HEART_RE = re.compile("[\u2764\u2765\u2665💕🧡💛💚💙💜🖤🤍🤎💖💗💓💞💘💝💟🫶]")


@dataclass(frozen=True)
class ComposedPost:
    texts: List[str]  # [本投稿, 自分リプ]
    item_code: str
    genre_id: str
    template_id: str


# 本投稿テンプレ: {short_name} {category} {rank} {review_avg} {review_count} {price}
# 方針:
#   - 1行目は42文字以内の「悩み・あるある・本音」フック（商品名から入らない）
#   - シロクマの脱力・正直トーンで統一
#   - 最後は問いかけで締めて返信を促す
_MAIN_TEMPLATES: Sequence[Tuple[str, str]] = (
    (
        "hook-honne",
        "正直、ランキング上位って疑ってかかるタイプ🐻‍❄️\n\n"
        "でも今日の{category}で見つけたこれ、\n"
        "レビュー{review_count}件で{review_avg}点は疑えなかった…\n\n"
        "「{short_name}」\n\n"
        "詳細はリプに置いとくね👇\n"
        "使ってる人いたら、実際どう？",
    ),
    (
        "hook-minna",
        "{category}って、結局みんな何買ってるんだろ?\n\n"
        "気になって楽天のランキング見てきた🐻‍❄️\n"
        "今日の上位にいたのがこれ。\n\n"
        "「{short_name}」\n"
        "{price}円でレビュー{review_avg}点。\n\n"
        "リプに詳細まとめた👇\n"
        "もう持ってる人いたら感想教えて",
    ),
    (
        "hook-teiten",
        "今日もランキング見てきたよ🐻‍❄️\n\n"
        "{category}でここ最近ずっと上位にいるのが\n"
        "「{short_name}」\n\n"
        "レビュー{review_avg}点（{review_count}件）。\n"
        "まあ、売れ続けてるのには理由がありそう。\n\n"
        "気になる人はリプ見て👇\n"
        "これ系で他におすすめあったら教えて",
    ),
    (
        "hook-price",
        "{price}円でレビュー{review_count}件って、何ごと?\n\n"
        "楽天の{category}ランキングで見つけた\n"
        "「{short_name}」🐻‍❄️\n\n"
        "安いから売れてるのか、良いから売れてるのか…\n"
        "スペックはリプに整理した👇\n\n"
        "買ったことある人いる？",
    ),
)

_REPLY_TEMPLATE = (
    "#PR\n"
    "アフィリエイトリンクを含みます\n\n"
    "【{short_name}】\n"
    "・価格: {price}円\n"
    "・レビュー: {review_avg}点（{review_count}件）\n"
    "{rank_line}"
    "・ショップ: {shop_name}\n"
    "{sale_block}"
    "\n気になった人はこちら↓\n"
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

    lines = sale_lines(on)
    sale_block = "".join(f"\n{line}" for line in lines) + ("\n" if lines else "")

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
        "sale_block": sale_block,
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


def compose_value(on: date, slot: int = 0, *, value_id: str | None = None) -> ComposedPost:
    """価値投稿（リンクなし・単発）を組み立てる。"""
    if value_id:
        from value_posts import _find

        post: ValuePost = _find(value_id)
    else:
        post = pick_value_post(on, slot)
    text = _truncate(post.text)
    if _URL_RE.search(text):
        raise ValueError("価値投稿にURLを含められません")
    if _HEART_RE.search(text):
        raise ValueError("価値投稿にハート系絵文字があります")
    if not text.strip():
        raise ValueError("価値投稿が空です")
    return ComposedPost(
        texts=[text],
        item_code=f"value:{post.value_id}",
        genre_id="",
        template_id=f"value-{post.value_id}",
    )
