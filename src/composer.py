"""商品データ → Threads 投稿文（テンプレート）。

制約（コードで強制）:
  - 本投稿・メモリプに URL 禁止（売り込みに見えない）
  - リンクは最終リプのみ。末尾に ※PR（景表法の広告明示）
  - MAX_TEXT_LEN 以下
  - ハート系絵文字なし
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
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
    texts: List[str]  # [本投稿, メモリプ, リンクリプ] or [単発]
    item_code: str
    genre_id: str
    template_id: str
    poll_options: List[str] = field(default_factory=list)
    image_url: str = ""


# 本投稿: らみ型（フック→キャッチ→場面→導入後の変化→問い）。
# 商品名・価格・URL・PR は出さない。「おすすめ」「コスパ」等の売り口調も使わない。
_MAIN_TEMPLATES: Sequence[Tuple[str, str]] = (
    (
        "hook-must",
        "↓また切れた…あるある↓\n\n"
        "＼先に置いとくだけ／\n\n"
        "{scene}、地味にキツい。\n"
        "{benefit}。\n\n"
        "同じことなってる人いる？",
    ),
    (
        "hook-scene",
        "↓場所あるある↓\n\n"
        "＼先置きメモ／\n\n"
        "{scene}、地味にキツい。\n"
        "{benefit}。\n\n"
        "みんなはどう凌いでる？",
    ),
    (
        "hook-tip",
        "↓切れてから走る↓\n\n"
        "＼先に置いとく／\n\n"
        "{problem}。\n"
        "{benefit}。\n\n"
        "先置き派、どれくらいいる？",
    ),
    (
        "hook-honest",
        "↓完璧じゃなくていい↓\n\n"
        "＼先置きで助かる／\n\n"
        "{scene}、正直キツい。\n"
        "{benefit}。\n\n"
        "正直なところ、どうしてる？",
    ),
    (
        "hook-heavy",
        "↓店で抱えて帰る↓\n\n"
        "＼届けてもらう／\n\n"
        "{problem}。\n"
        "{benefit}。\n\n"
        "ネット寄せた人、楽になった？",
    ),
)

# リプ1: うちのストックメモ（会話の続き）。リンク・PR・価格なし。
# 導入後の変化を1文入れて、本投稿の続きにする。
_REPLY_MEMO = (
    "うちのストックはこれ。\n"
    "{short_name}\n\n"
    "先置きしてからの方が楽。\n"
    "{avoid}"
    "{sale_block}"
)

# リプ2: 欲しい人だけ。URL + ※PR（景表法の広告明示はここだけ）
_REPLY_LINK = (
    "{affiliate_url}\n"
    "※PR"
)

# 後方互換: 旧ID指定が来ても新テンプレへ寄せる
_TEMPLATE_ALIASES = {
    "hook-benefit": "hook-must",
    "hook-stock": "hook-scene",
    "hook-tonight": "hook-honest",
    "hook-reason": "hook-tip",
}

_PR_DISCLOSURE = "※PR"
# リプ内の商品名表示上限
_REPLY_NAME_LIMIT = 28
# ソフト上限（ハードは MAX_TEXT_LEN）。テストと運用の目安
# らみ型フック＋導入後の変化を入れるため本投稿はやや余裕を持たせる
_SOFT_MAIN_LIMIT = 140
_SOFT_MEMO_LIMIT = 180
_SOFT_LINK_LIMIT = 120
# 後方互換
_SOFT_REPLY_LIMIT = _SOFT_MEMO_LIMIT


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


def _short_name_for_reply(name: str, limit: int = _REPLY_NAME_LIMIT) -> str:
    name = (name or "").strip()
    if len(name) <= limit:
        return name
    return name[: limit - 1] + "…"


def _validate(texts: List[str]) -> None:
    if len(texts) < 3:
        raise ValueError("本投稿・メモリプ・リンクリプの3本が必要です")
    main, memo, link = texts[0], texts[1], texts[2]
    if _URL_RE.search(main) or _URL_RE.search(memo):
        raise ValueError("本投稿・メモリプにURLを含められません")
    if _PR_DISCLOSURE not in link:
        raise ValueError(f"リンクリプに「{_PR_DISCLOSURE}」が必要です")
    if not _URL_RE.search(link):
        raise ValueError("リンクリプにURLが必要です")
    joined = "\n".join(texts)
    for bad in ("正体はこれ", "▼商品はこちら", "アフィリエイトリンク", "#PR"):
        if bad in joined:
            raise ValueError(f"売り込み口調「{bad}」は使わない")
    if "アフィリエイト" in joined:
        raise ValueError("本文に「アフィリエイト」を出さない")
    if _PR_DISCLOSURE in main or _PR_DISCLOSURE in memo:
        raise ValueError("※PR は最終リプのみ")
    # 本投稿に売り込みラベル / 商品名の先出しが混ざっていないか
    for bad in ("このままだと:", "これを置くと:", "Before:", "After:", "困り:", "解決:", "「", "」"):
        if bad in main:
            raise ValueError(f"本投稿に機械的なラベル/商品名括弧「{bad}」があります")
    for bad in ("円", "レビュー", "おすすめ", "コスパ"):
        if bad in main:
            raise ValueError(f"本投稿に売り込み語「{bad}」があります")
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

    from sale import sale_lines

    # カレンダー上の今日買う理由だけ。送料込・クーポン気配はカタログ感が出るので入れない。
    deal = sale_lines(on)[:1]
    sale_block = f"\n{deal[0]}" if deal else ""

    fields = {
        "short_name": _short_name_for_reply(item.short_name),
        "category": pick.genre.short,
        "affiliate_url": item.affiliate_url,
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
    memo = _truncate(_REPLY_MEMO.format(**fields))
    link = _truncate(_REPLY_LINK.format(**fields))
    texts = [main, memo, link]
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


def compose_ogiri(on: date, slot: int = 0) -> ComposedPost:
    """ジブリ大喜利（画像＋短文・リンクなし）。"""
    from ogiri_posts import pick_ogiri

    row = pick_ogiri(on=on, slot=slot)
    text = _truncate(str(row.get("text") or ""))
    image_url = str(row.get("image_url") or "").strip()
    pid = str(row.get("id") or "").strip() or "ogiri-unknown"
    if not text:
        raise ValueError("大喜利本文が空です")
    if not image_url:
        raise ValueError(f"大喜利画像がありません id={pid}")
    _validate_generic([text])
    return ComposedPost(
        texts=[text],
        item_code=f"value:{pid}",
        genre_id="",
        template_id=f"ogiri-{pid}",
        image_url=image_url,
    )


def compose_value(on: date, slot: int = 0, *, value_id: str | None = None) -> ComposedPost:
    """価値投稿（リンクなし・単発）を組み立てる。アンケート枠は poll_options 付き。"""
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
    poll = [str(o).strip() for o in (post.poll_options or ()) if str(o).strip()]
    if poll and (len(poll) < 2 or len(poll) > 4):
        raise ValueError(f"poll_options は 2〜4 個必要です: {poll}")
    for opt in poll:
        if len(opt) > 25:
            raise ValueError(f"poll option が25字超: {opt}")
    return ComposedPost(
        texts=[text],
        item_code=f"value:{post.value_id}",
        genre_id="",
        template_id=f"value-{post.value_id}",
        poll_options=poll,
    )
