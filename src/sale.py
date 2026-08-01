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
    """リプに追記するセール系の「今日買う理由」行。"""
    lines: list[str] = []
    label = active_sale_label(on)
    if label:
        lines.append(f"いま{label}の期間中。買うならこのタイミングかも")
    if is_zero_five_day(on):
        lines.append(config.ZERO_FIVE_DAY_LINE)
    return lines


_COUPON_RE = re.compile(r"クーポン|coupon|％OFF|%OFF|ポイント最大|P\d+倍", re.IGNORECASE)


def item_deal_lines(item: "RakutenItem", on: date) -> List[str]:
    """⑧ 商品ごとの今日買う理由（ポイント・送料・クーポン気配）。"""
    lines: List[str] = []
    lines.extend(sale_lines(on))
    if getattr(item, "point_rate", 0) and item.point_rate >= 2:
        lines.append(f"いまポイント{item.point_rate}倍表記あり。倍率は購入前に公式で再確認してね")
    if _COUPON_RE.search(item.item_name or ""):
        lines.append("商品名にクーポン/倍率の気配あり。取得ボタン押し忘れに注意")
    if getattr(item, "postage_flag", None) == 0:
        # postageFlag: 0=送料別 / 1=送料込 というドキュメントが多いが
        # 実データ差があるため、送料込の断定はしない。別途39ショップ案内のみ。
        pass
    if not lines:
        lines.append("急ぎでなければ、5と0のつく日かセールに寄せるのも手")
    return lines
