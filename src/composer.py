"""商品データ → Threads 投稿文（テンプレート）。

制約（コードで強制）:
  - 本投稿に URL 禁止
  - リンクリプに ※PR（アフィリエイトリンク） を含める（リンク直後）
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


# 本投稿テンプレ（人気投稿寄り・短め）:
#   痛み1行 → 短い共感/困り 1〜2行 → 商品名 → リプ誘導1つ
#   価格・レビュー・注意点は本投稿に置かない
#   benefit は本投稿かリプのどちらか一方（リプでは繰り返さない）
#   「このままだと:」「Before:」などラベル調は使わない
_MAIN_TEMPLATES: Sequence[Tuple[str, str]] = (
    (
        "hook-must",
        "{pain}\n\n"
        "これ、ないと地味に詰む。\n"
        "{problem}\n\n"
        "「{short_name}」\n\n"
        "気になる人はリプに👇",
    ),
    (
        "hook-scene",
        "{pain}\n\n"
        "{scene}、わかる人いる？\n"
        "{benefit}\n\n"
        "「{short_name}」\n\n"
        "リプに置いとくね👇",
    ),
    (
        "hook-tip",
        "{pain}\n\n"
        "おすすめは、切れる前に宅配で足しとくこと。\n"
        "{benefit}\n\n"
        "「{short_name}」\n\n"
        "気になる人はリプへ👇",
    ),
    (
        "hook-honest",
        "{pain}\n\n"
        "完璧な商品じゃないけど、切れてからの寄り道の方がキツい。\n"
        "{benefit}\n\n"
        "「{short_name}」\n\n"
        "使ってる人いたら教えて👇",
    ),
    (
        "hook-heavy",
        "{pain}\n\n"
        "店で抱えて帰るの、いちばんコスパ悪い。\n"
        "{problem}\n\n"
        "「{short_name}」\n\n"
        "もうネット寄せた人、楽になった？👇",
    ),
)

# リプは「続き置き場」。本編の繰り返しなし。注意点→価格→リンク→PR
_REPLY_TEMPLATE = (
    "正直、{avoid}\n\n"
    "{price}円 / レビュー{review_avg}点（{review_count}件）"
    "{rank_line}"
    "{sale_block}"
    "\n\n▼商品はこちら\n"
    "{affiliate_url}\n"
    "\n※PR（アフィリエイトリンク）"
)

# 後方互換: 旧ID指定が来ても新テンプレへ寄せる
_TEMPLATE_ALIASES = {
    "hook-benefit": "hook-must",
    "hook-stock": "hook-scene",
    "hook-tonight": "hook-honest",
    "hook-reason": "hook-tip",
}

_PR_DISCLOSURE = "※PR（アフィリエイトリンク）"
# 本投稿の商品名は短く（長い正式名は離脱しやすい）
_MAIN_NAME_LIMIT = 24
# ソフト上限（ハードは MAX_TEXT_LEN）。テストと運用の目安
_SOFT_MAIN_LIMIT = 140
_SOFT_REPLY_LIMIT = 360


def _fmt_price(n: int) -> str:
    return f"{n:,}"


def _resolve_template_id(tid: str) -> str:
    return _TEMPLATE_ALIASES.get(tid, tid)


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


def _short_name_for_main(name: str, limit: int = _MAIN_NAME_LIMIT) -> str:
    name = (name or "").strip()
    if len(name) <= limit:
        return name
    return name[: limit - 1] + "…"


def _validate(texts: List[str]) -> None:
    if len(texts) < 2:
        raise ValueError("本投稿とリプの2本が必要です")
    main, reply = texts[0], texts[1]
    if _URL_RE.search(main):
        raise ValueError("本投稿にURLを含められません")
    if _PR_DISCLOSURE not in reply:
        raise ValueError(f"リンクリプに「{_PR_DISCLOSURE}」が必要です")
    # 本投稿に売り込みラベルが混ざっていないか（テンプレ退行検知）
    for bad in ("このままだと:", "これを置くと:", "Before:", "After:", "困り:", "解決:"):
        if bad in main:
            raise ValueError(f"本投稿に機械的なラベル「{bad}」があります")
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
    pain = pick.pain
    if template_id:
        tid = template_id
    elif pain and pain.template_id:
        tid = pain.template_id
    else:
        tid = _pick_template_id(item.item_code, on, pick.slot)
    tid = _resolve_template_id(tid)
    templates = {k: v for k, v in _MAIN_TEMPLATES}
    if tid not in templates:
        raise ValueError(f"未知の template_id: {tid}")

    from sale import item_deal_lines

    deal_lines = item_deal_lines(item, on)
    # リプは短く保つ。セール行は最大2本まで
    sale_block = "".join(f"\n{line}" for line in deal_lines[:2])

    fields = {
        "short_name": _short_name_for_main(item.short_name),
        "category": pick.genre.short,
        "rank": item.rank or "?",
        "review_avg": f"{item.review_average:.1f}",
        "review_count": f"{item.review_count:,}",
        "price": _fmt_price(item.item_price),
        "shop_name": item.shop_name or "楽天市場",
        "affiliate_url": item.affiliate_url,
        # 順位は補足。無ければ行ごと省略
        "rank_line": f" / {item.rank}位付近" if item.rank else "",
        "sale_block": sale_block,
        "pain": (pain.pain if pain else "今夜の買い足し、迷ってる人へ"),
        "pain_short": (pain.pain.rstrip("？?") if pain else "家庭の買い足し"),
        "scene": (pain.scene if pain else "切れそうな消耗品を先に足すとき"),
        "problem": (
            pain.problem
            if pain
            else "切れてから買うと、忙しい夜に余計な寄り道が発生する"
        ),
        "benefit": (
            pain.benefit
            if pain
            else "先にストックしておけば、夜の自分が助かる"
        ),
        "buy_reason": (
            pain.buy_reason if pain else "切れてから走るより、先に足した方が楽"
        ),
        "avoid": (pain.avoid if pain else "サイズ・香り・容量は要確認"),
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


# ダイジェスト用: TOP3の下に添える一言（日付ローテ）
_DIGEST_COMMENTS: Sequence[str] = (
    "家庭の定番って、だいたいこのへんに居座るんだよね",
    "しばらく順位が動かないやつは、リピ勢が支えてる証拠",
    "急に入ってきた新顔は、セール玉のことが多いから様子見",
    "買い足しタイミングと重なると、顔ぶれが一気に動く",
)


def _shorten(name: str, limit: int = 28) -> str:
    name = name.strip()
    return name if len(name) <= limit else name[: limit - 1] + "…"


def _validate_generic(texts: List[str]) -> None:
    for i, t in enumerate(texts):
        if _URL_RE.search(t):
            raise ValueError(f"texts[{i}] にURLを含められません")
        if _HEART_RE.search(t):
            raise ValueError(f"texts[{i}] にハート系絵文字があります")
        if len(t) > config.MAX_TEXT_LEN:
            raise ValueError(f"texts[{i}] が長すぎます ({len(t)} > {config.MAX_TEXT_LEN})")
        if not t.strip():
            raise ValueError(f"texts[{i}] が空です")


def compose_digest(client, on: date, slot: int, *, fmt: str | None = None) -> ComposedPost:
    """ランキングダイジェスト（リンクなし・毎日内容が変わる価値投稿）。

    fmt: top3 / quiz / sleeper。省略時は日付×枠でローテ。
    """
    from picker import genre_for_slot

    genre = genre_for_slot(slot, on)
    ranking = client.fetch_ranking(genre.id, hits=10)
    if len(ranking) < 3:
        raise RuntimeError(f"ダイジェストに必要な件数が取れません genre={genre.id}")

    # 枠のインデックス（slot番号そのものだと mod 3 で同日衝突するため）でローテ
    k = config.DIGEST_SLOTS.index(slot) if slot in config.DIGEST_SLOTS else slot
    fmt = fmt or ("top3", "quiz", "sleeper")[(on.toordinal() + k) % 3]
    names = [_shorten(i.short_name) for i in ranking]

    if fmt == "top3":
        comment = _DIGEST_COMMENTS[(on.toordinal() + slot) % len(_DIGEST_COMMENTS)]
        texts = [
            f"今日の家庭向け{genre.short}ランキング、上位メモ\n\n"
            f"1位 {names[0]}\n"
            f"2位 {names[1]}\n"
            f"3位 {names[2]}\n\n"
            f"{comment}。\n\n"
            f"この中で、家のストックに欲しいのあった？"
        ]
    elif fmt == "quiz":
        top = ranking[0]
        texts = [
            f"【クイズ】今日の{genre.short}買い足しランキング\n\n"
            f"2位 {names[1]}\n"
            f"3位 {names[2]}\n\n"
            f"さて、1位はなんでしょう?\n"
            f"ヒント: レビュー{top.review_count:,}件のあれ。\n\n"
            f"答えはリプに置いとくね👇",
            f"正解は…\n\n"
            f"「{names[0]}」でした\n"
            f"レビュー{top.review_average:.1f}点（{top.review_count:,}件）。\n\n"
            f"家で使ってる人、当たった？",
        ]
    elif fmt == "sleeper":
        tail = ranking[-3:]
        lines = "\n".join(f"・{_shorten(i.short_name)}" for i in tail)
        texts = [
            f"1位より「じわじわ買い足されてるゾーン」が好きなんだよね\n\n"
            f"今日の{genre.short}ランキング、\n"
            f"上位のすぐ下にいたのがこのへん。\n\n"
            f"{lines}\n\n"
            f"派手じゃないけど、家庭の定番候補はだいたいここにいる。\n\n"
            f"使ってるのあったら教えて"
        ]
    else:
        raise ValueError(f"未知のダイジェスト形式: {fmt}")

    texts = [_truncate(t) for t in texts]
    _validate_generic(texts)
    return ComposedPost(
        texts=texts,
        item_code=f"digest:{fmt}:{genre.id}",
        genre_id=genre.id,
        template_id=f"digest-{fmt}",
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
