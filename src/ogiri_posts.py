"""ジブリ場面写真 × 買い足し大喜利（かいものくま）.

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
        "id": "ogiri-chihiro-detergent",
        "kind": "ogiri",
        "image_url": _still("chihiro001"),
        "text": "洗剤切れに気づいた瞬間の、後ろの席の顔",
    },
    {
        "id": "ogiri-chihiro-bill",
        "kind": "ogiri",
        "image_url": _still("chihiro016"),
        "text": "レジで合計見た瞬間、予想の1.5倍だった時",
    },
    {
        "id": "ogiri-chihiro-stock",
        "kind": "ogiri",
        "image_url": _still("chihiro030"),
        "text": "ストック棚、同じやつが3個あるのにまたカゴへ",
    },
    {
        "id": "ogiri-totoro-heavy",
        "kind": "ogiri",
        "image_url": _still("totoro001"),
        "text": "水6本、雨の日に抱えて帰る決意をした顔",
    },
    {
        "id": "ogiri-totoro-rain",
        "kind": "ogiri",
        "image_url": _still("totoro012"),
        "text": "ポイント日なのに、カゴの中身が増えすぎてる",
    },
    {
        "id": "ogiri-majo-delivery",
        "kind": "ogiri",
        "image_url": _still("majo020"),
        "text": "宅配ボックス満杯で、詰め替えが玄関で待ってる",
    },
    {
        "id": "ogiri-majo-empty",
        "kind": "ogiri",
        "image_url": _still("majo001"),
        "text": "「まだある」って言ったボトル、もう空気だけ",
    },
    {
        "id": "ogiri-howl-messy",
        "kind": "ogiri",
        "image_url": _still("howl012"),
        "text": "キッチン、消耗品の空パックだけが増えていく城",
    },
    {
        "id": "ogiri-howl-calc",
        "kind": "ogiri",
        "image_url": _still("howl008"),
        "text": "まとめ買い、本当にお得か計算してフリーズする",
    },
    {
        "id": "ogiri-mononoke-stare",
        "kind": "ogiri",
        "image_url": _still("mononoke010"),
        "text": "詰め替えと本体、どっちが得か棚の前で睨む",
    },
    {
        "id": "ogiri-ponyo-ham",
        "kind": "ogiri",
        "image_url": _still("ponyo008"),
        "text": "特売ハム見て、カゴに入れる手が止まらない",
    },
    {
        "id": "ogiri-laputa-robot",
        "kind": "ogiri",
        "image_url": _still("laputa005"),
        "text": "重い日用品、宅配に寄せたあとのロボット感",
    },
    {
        "id": "ogiri-porco-cool",
        "kind": "ogiri",
        "image_url": _still("porco008"),
        "text": "ポイント日を知ってる顔で、カートを押してる",
    },
    {
        "id": "ogiri-marnie-window",
        "kind": "ogiri",
        "image_url": _still("marnie005"),
        "text": "ネット注文したのに、届くまで中身を忘れる窓際",
    },
    {
        "id": "ogiri-nausicaa-wind",
        "kind": "ogiri",
        "image_url": _still("nausicaa001"),
        "text": "値上げの風、日用品コーナーにだけ強く当たってる",
    },
    {
        "id": "ogiri-yamada-dinner",
        "kind": "ogiri",
        "image_url": _still("yamada001"),
        "text": "ラップ切れ、夕飯の残りをどう保存するか会議",
    },
    {
        "id": "ogiri-tanuki-shelf",
        "kind": "ogiri",
        "image_url": _still("tanuki001"),
        "text": "同じ洗剤なのに、パッケージだけ変身してる棚",
    },
    {
        "id": "ogiri-baron-pose",
        "kind": "ogiri",
        "image_url": _still("baron005"),
        "text": "ストック先置きしただけで、賢くなった気がする",
    },
    {
        "id": "ogiri-karigurashi-tiny",
        "kind": "ogiri",
        "image_url": _still("karigurashi001"),
        "text": "詰め替え、最後の一滴まで絞ってる小さな戦い",
    },
    {
        "id": "ogiri-kazetachinu-desk",
        "kind": "ogiri",
        "image_url": _still("kazetachinu005"),
        "text": "買い物リスト書いたのに、店で別のやつ入れてる",
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
