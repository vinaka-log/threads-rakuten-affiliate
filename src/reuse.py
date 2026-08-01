"""伸びた価値投稿の再利用キュー。

参考運用（3日に1回再利用）に合わせ、価値投稿をキュー管理する。
- 通常投稿時に自動登録
- REUSE_INTERVAL_DAYS 経過後、REUSE_SLOTS で優先投下
- 任意で Threads Insights の views/likes を取り込み優先度を上げる
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import config
from picker import load_ledger
from value_posts import _find

JST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class ReuseCandidate:
    value_id: str
    last_posted_on: str
    reuse_count: int = 0
    priority: int = 0
    views: int = 0
    likes: int = 0
    replies: int = 0
    source: str = "auto"
    threads_post_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value_id": self.value_id,
            "last_posted_on": self.last_posted_on,
            "reuse_count": self.reuse_count,
            "priority": self.priority,
            "views": self.views,
            "likes": self.likes,
            "replies": self.replies,
            "source": self.source,
            "threads_post_id": self.threads_post_id,
        }


def _today() -> date:
    return datetime.now(JST).date()


def load_reuse(path: Path = config.REUSE_PATH) -> List[ReuseCandidate]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("candidates") if isinstance(raw, dict) else raw
    out: List[ReuseCandidate] = []
    for e in items or []:
        if not isinstance(e, dict):
            continue
        vid = str(e.get("value_id") or "").strip()
        last = str(e.get("last_posted_on") or "").strip()
        if not vid or not last:
            continue
        out.append(
            ReuseCandidate(
                value_id=vid,
                last_posted_on=last,
                reuse_count=int(e.get("reuse_count") or 0),
                priority=int(e.get("priority") or 0),
                views=int(e.get("views") or 0),
                likes=int(e.get("likes") or 0),
                replies=int(e.get("replies") or 0),
                source=str(e.get("source") or "auto"),
                threads_post_id=str(e.get("threads_post_id") or ""),
            )
        )
    return out


def save_reuse(candidates: List[ReuseCandidate], path: Path = config.REUSE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # value_id 単位で最新を残す（重複排除）
    by_id: Dict[str, ReuseCandidate] = {}
    for c in candidates:
        prev = by_id.get(c.value_id)
        if prev is None or c.last_posted_on >= prev.last_posted_on:
            by_id[c.value_id] = c
    ordered = sorted(
        by_id.values(),
        key=lambda c: (-c.priority, -c.views, -c.likes, c.last_posted_on),
    )
    payload = {
        "updated_at": datetime.now(JST).isoformat(timespec="seconds"),
        "candidates": [c.to_dict() for c in ordered],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _score(c: ReuseCandidate) -> tuple:
    engagement = c.views + c.likes * 10 + c.replies * 20
    return (c.priority, engagement, c.reuse_count == 0)


def _posted_value_ids_on(on: date, ledger_path: Path = config.LEDGER_PATH) -> set[str]:
    ids: set[str] = set()
    for e in load_ledger(ledger_path):
        if str(e.get("posted_on") or "") != on.isoformat():
            continue
        code = str(e.get("item_code") or "")
        if code.startswith("value:"):
            ids.add(code.split(":", 1)[-1])
    return ids


def is_due(c: ReuseCandidate, on: date, *, interval_days: int = config.REUSE_INTERVAL_DAYS) -> bool:
    try:
        last = date.fromisoformat(c.last_posted_on)
    except ValueError:
        return False
    return (on - last).days >= interval_days


def pick_reuse_value(
    on: Optional[date] = None,
    *,
    slot: int = 0,
    path: Path = config.REUSE_PATH,
    ledger_path: Path = config.LEDGER_PATH,
) -> Optional[ReuseCandidate]:
    """再利用枠向けに、期限到来かつ当日未投稿の候補を1件返す。"""
    on = on or _today()
    used_today = _posted_value_ids_on(on, ledger_path)
    due = [
        c
        for c in load_reuse(path)
        if is_due(c, on) and c.value_id not in used_today
    ]
    if not due:
        return None
    # 存在しない ID はスキップ
    valid: List[ReuseCandidate] = []
    for c in due:
        try:
            _find(c.value_id)
            valid.append(c)
        except KeyError:
            continue
    if not valid:
        return None
    valid.sort(key=_score, reverse=True)
    return valid[0]


def register_value_post(
    *,
    value_id: str,
    posted_on: str,
    threads_post_ids: Optional[List[str]] = None,
    source: str = "auto",
    priority: int = 0,
    path: Path = config.REUSE_PATH,
) -> ReuseCandidate:
    """価値投稿を再利用キューに登録/更新。"""
    _find(value_id)  # 存在確認
    candidates = load_reuse(path)
    existing = next((c for c in candidates if c.value_id == value_id), None)
    post_id = ""
    if threads_post_ids:
        post_id = str(threads_post_ids[0])
    if existing:
        updated = ReuseCandidate(
            value_id=value_id,
            last_posted_on=posted_on,
            reuse_count=existing.reuse_count + (1 if source == "reuse" else 0),
            priority=max(existing.priority, priority),
            views=existing.views,
            likes=existing.likes,
            replies=existing.replies,
            source=existing.source if existing.source == "seed" else source,
            threads_post_id=post_id or existing.threads_post_id,
        )
        candidates = [updated if c.value_id == value_id else c for c in candidates]
    else:
        updated = ReuseCandidate(
            value_id=value_id,
            last_posted_on=posted_on,
            reuse_count=1 if source == "reuse" else 0,
            priority=priority,
            source=source,
            threads_post_id=post_id,
        )
        candidates.append(updated)
    save_reuse(candidates, path)
    return updated


def mark_winner(
    value_id: str,
    *,
    priority: int = 10,
    path: Path = config.REUSE_PATH,
) -> ReuseCandidate:
    """手動で伸びた投稿を高優先度にする。"""
    _find(value_id)
    candidates = load_reuse(path)
    existing = next((c for c in candidates if c.value_id == value_id), None)
    last = existing.last_posted_on if existing else (_today() - timedelta(days=config.REUSE_INTERVAL_DAYS)).isoformat()
    updated = ReuseCandidate(
        value_id=value_id,
        last_posted_on=last,
        reuse_count=existing.reuse_count if existing else 0,
        priority=max(priority, existing.priority if existing else 0),
        views=existing.views if existing else 0,
        likes=existing.likes if existing else 0,
        replies=existing.replies if existing else 0,
        source="manual",
        threads_post_id=existing.threads_post_id if existing else "",
    )
    others = [c for c in candidates if c.value_id != value_id]
    others.append(updated)
    save_reuse(others, path)
    return updated


def apply_insights(
    metrics_by_post_id: Dict[str, Dict[str, int]],
    *,
    path: Path = config.REUSE_PATH,
    winner_views: int = config.REUSE_WINNER_MIN_VIEWS,
) -> int:
    """insights 結果をキューに反映。戻り値は更新件数。"""
    candidates = load_reuse(path)
    if not candidates:
        return 0
    updated_n = 0
    out: List[ReuseCandidate] = []
    for c in candidates:
        m = metrics_by_post_id.get(c.threads_post_id) if c.threads_post_id else None
        if not m:
            out.append(c)
            continue
        views = int(m.get("views") or 0)
        likes = int(m.get("likes") or 0)
        replies = int(m.get("replies") or 0)
        bump = 0
        if views >= winner_views:
            bump = 10
        elif views >= max(1, winner_views // 3):
            bump = 5
        out.append(
            ReuseCandidate(
                value_id=c.value_id,
                last_posted_on=c.last_posted_on,
                reuse_count=c.reuse_count,
                priority=max(c.priority, bump),
                views=views,
                likes=likes,
                replies=replies,
                source=c.source,
                threads_post_id=c.threads_post_id,
            )
        )
        updated_n += 1
    save_reuse(out, path)
    return updated_n


def backfill_from_ledger(
    *,
    ledger_path: Path = config.LEDGER_PATH,
    path: Path = config.REUSE_PATH,
) -> int:
    """台帳の静的価値投稿をキューへ取り込む（digest は除外）。"""
    added = 0
    for e in load_ledger(ledger_path):
        code = str(e.get("item_code") or "")
        if not code.startswith("value:"):
            continue
        vid = code.split(":", 1)[-1]
        # digest 由来の value:top3:.. 等は静的プールにないのでスキップ
        if ":" in vid:
            continue
        try:
            _find(vid)
        except KeyError:
            continue
        ids = e.get("threads_post_ids") or []
        register_value_post(
            value_id=vid,
            posted_on=str(e.get("posted_on") or _today().isoformat()),
            threads_post_ids=[str(x) for x in ids] if isinstance(ids, list) else None,
            source="ledger",
        )
        added += 1
    return added
