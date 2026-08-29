"""ジブリ場面写真 × ベビー買い足し大喜利（かいものくま）.

画像はスタジオジブリ公式ギャラリー（常識の範囲で自由利用可）。
https://www.ghibli.jp/gallery/*.jpg

PR・URL・商品名は入れない。1投稿完結・画像＋短文のみ。
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List, Set

import config

GHIBLI_GALLERY = "https://www.ghibli.jp/gallery"


def _still(name: str) -> str:
    return f"{GHIBLI_GALLERY}/{name}.jpg"


OGIRI_POSTS: List[dict] = [
    {
        "id": "ogiri-chihiro-rain",
        "kind": "ogiri",
        "image_url": _still("chihiro001"),
        "text": "レインカバー忘れて、空が怪しくなった瞬間の顔",
    },
    {
        "id": "ogiri-chihiro-bag",
        "kind": "ogiri",
        "image_url": _still("chihiro016"),
        "text": "おむつ・おしりふき・着替え…カバンが荷物室になってる",
    },
    {
        "id": "ogiri-chihiro-night",
        "kind": "ogiri",
        "image_url": _still("chihiro030"),
        "text": "夜中のおむつ替え、床のおむつ山を探すタイム",
    },
    {
        "id": "ogiri-totoro-stroll",
        "kind": "ogiri",
        "image_url": _still("totoro001"),
        "text": "ベビーカーで外出、両手が足りなくて立ち止まる",
    },
    {
        "id": "ogiri-totoro-sleep",
        "kind": "ogiri",
        "image_url": _still("totoro012"),
        "text": "寝かしつけ完了…と思ったらまた起きてる",
    },
    {
        "id": "ogiri-majo-delivery",
        "kind": "ogiri",
        "image_url": _still("majo020"),
        "text": "ベビーグッズの宅配、玄関で段ボールが増えていく",
    },
    {
        "id": "ogiri-majo-size",
        "kind": "ogiri",
        "image_url": _still("majo001"),
        "text": "おむつサイズ、まだいけると思った翌週にモレる",
    },
    {
        "id": "ogiri-howl-messy",
        "kind": "ogiri",
        "image_url": _still("howl012"),
        "text": "子ども服、床に増殖して朝の戦場になる部屋",
    },
    {
        "id": "ogiri-howl-calc",
        "kind": "ogiri",
        "image_url": _still("howl008"),
        "text": "抱っこひも比較表、見すぎて夜更かしする",
    },
    {
        "id": "ogiri-mononoke-stare",
        "kind": "ogiri",
        "image_url": _still("mononoke010"),
        "text": "手形スタンプ、汚れるか怖くて棚の前で睨む",
    },
    {
        "id": "ogiri-ponyo-bath",
        "kind": "ogiri",
        "image_url": _still("ponyo008"),
        "text": "沐浴上がり、薄手タオルで急いで包むタイムアタック",
    },
    {
        "id": "ogiri-laputa-robot",
        "kind": "ogiri",
        "image_url": _still("laputa005"),
        "text": "お出かけセット整えたあとの、ちょっと強い気持ち",
    },
    {
        "id": "ogiri-porco-cool",
        "kind": "ogiri",
        "image_url": _still("porco008"),
        "text": "ポイント日にベビーグッズをカゴへ入れる顔",
    },
    {
        "id": "ogiri-marnie-window",
        "kind": "ogiri",
        "image_url": _still("marnie005"),
        "text": "ネット注文した枕、届くまで月齢を忘れる窓際",
    },
    {
        "id": "ogiri-nausicaa-wind",
        "kind": "ogiri",
        "image_url": _still("nausicaa001"),
        "text": "急な雨雲、ベビーカー席にだけ強く当たってる",
    },
    {
        "id": "ogiri-yamada-dinner",
        "kind": "ogiri",
        "image_url": _still("yamada001"),
        "text": "離乳食のあと、床の食べこぼし会議が始まる",
    },
    {
        "id": "ogiri-tanuki-shelf",
        "kind": "ogiri",
        "image_url": _still("tanuki001"),
        "text": "同じおむつなのに、パッケージだけ変身してる棚",
    },
    {
        "id": "ogiri-baron-pose",
        "kind": "ogiri",
        "image_url": _still("baron005"),
        "text": "先に揃えただけで、育児が少し賢くなった気がする",
    },
    {
        "id": "ogiri-karigurashi-tiny",
        "kind": "ogiri",
        "image_url": _still("karigurashi001"),
        "text": "おしりふき、携帯用の最後の一枚を節約する戦い",
    },
    {
        "id": "ogiri-kazetachinu-desk",
        "kind": "ogiri",
        "image_url": _still("kazetachinu005"),
        "text": "買い物リスト書いたのに、店で別のベビー用品入れてる",
    },
]


def _used_ids(ledger_path: Path | None = None) -> Set[str]:
    from picker import load_ledger

    used: Set[str] = set()
    for entry in load_ledger(ledger_path or config.LEDGER_PATH):
        code = str(entry.get("item_code") or "")
        if code.startswith("value:ogiri-"):
            used.add(code.split(":", 1)[-1])
        elif code.startswith("ogiri-"):
            used.add(code)
        vid = str(entry.get("value_id") or "")
        if vid.startswith("ogiri-"):
            used.add(vid)
    return used


def unused_ogiri_posts(
    extra_used: Set[str] | None = None,
    *,
    ledger_path: Path | None = None,
) -> List[dict]:
    used = _used_ids(ledger_path) | (extra_used or set())
    return [p for p in OGIRI_POSTS if str(p.get("id") or "") not in used]


def pick_ogiri(
    *,
    extra_used: Set[str] | None = None,
    on: date | None = None,
    slot: int = 0,
    ledger_path: Path | None = None,
) -> dict:
    """未使用の大喜利を1本返す。枯渇時は日付×枠で再利用。"""
    unused = unused_ogiri_posts(extra_used, ledger_path=ledger_path)
    if unused:
        return dict(unused[0])
    on = on or date.today()
    idx = (on.toordinal() * max(1, len(getattr(config, "OGIRI_SLOTS", (0,)) or (0,))) + slot) % len(
        OGIRI_POSTS
    )
    return dict(OGIRI_POSTS[idx])
