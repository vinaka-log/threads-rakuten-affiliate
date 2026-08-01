"""楽天セールイベントの判定（5と0のつく日・セール期間）。"""

from __future__ import annotations

from datetime import date
from typing import Optional

import config


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
    """リプに追記する「今日買う理由」行のリスト。"""
    lines: list[str] = []
    label = active_sale_label(on)
    if label:
        lines.append(f"いま{label}の期間中。買うならこのタイミングかも")
    if is_zero_five_day(on):
        lines.append(config.ZERO_FIVE_DAY_LINE)
    return lines
