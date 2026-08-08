"""楽天セールイベントの判定（5と0のつく日・セール期間）+ 今日買う理由。"""

from __future__ import annotations

import re
from datetime import date
from typing import TYPE_CHECKING, List, Optional

import config

if TYPE_CHECKING:
    from rakuten import RakutenItem


def is_zero_five_day(on: date) -> bool:
    """5と0のつく日（5,10,15,20,25,30日）かどうか。"""
    return on.day % 5 == 0


def active_sale_label(on: date) -> Optional[str]:
    """開催中のセール名（お買い物マラソン等）。なければ None。"""
    for start, end, label in config.SALE_PERIODS:
        if date.fromisoformat(start) <= on <= date.fromisoformat(end):
            return label
    return None


def sale_lines(on: date) -> list[str]:
    """リプに追記するセール系の「今日買う理由」行（短め）。"""
    lines: list[str] = []
    label = active_sale_label(on)
    if label:
        lines.append(f"いま{label}中")
    if is_zero_five_day(on):
        lines.append(config.ZERO_FIVE_DAY_LINE)
    return lines


_COUPON_RE = re.compile(r"クーポン|coupon|％OFF|%OFF|ポイント最大|P\d+倍", re.IGNORECASE)


def item_deal_lines(item: "RakutenItem", on: date) -> List[str]:
    """⑧ 商品ごとの今日買う理由（ポイント・送料・クーポン気配）。短文優先。"""
    lines: List[str] = []
    lines.extend(sale_lines(on))
    if getattr(item, "point_rate", 0) and item.point_rate >= 2:
        lines.append(f"ポイント{item.point_rate}倍表記あり（購入前に再確認）")
    if _COUPON_RE.search(item.item_name or ""):
        lines.append("クーポン気配あり。取得ボタン押し忘れ注意")
    # 応答 postageFlag: 0=送料込 / 1=送料別（公式）
    postage = getattr(item, "postage_flag", None)
    if postage == 0:
        lines.append("送料込表記")
    elif postage == 1:
        lines.append("送料別表記あり・合計要確認")
    if not lines:
        lines.append("急ぎじゃなければ5と0の日もアリ")
    return lines
