"""どうでもいい雑談の自動生成・補充。

方針:
  - 雑談は一度きり（台帳で消費）。足りなくなったらここで足す
  - 既定はパーツ組み合わせ（外部API不要）
  - OPENAI_API_KEY または CHITCHAT_LLM_API_KEY があれば LLM で下書き生成
  - 日用品・共働き家事ネタには寄せない（AI運用アカウントに見えないブレ用）
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Sequence

import config

JST = timezone(timedelta(hours=9))

CHITCHAT_POOL_PATH = config.CHITCHAT_POOL_PATH
MIN_UNUSED = int(config.CHITCHAT_MIN_UNUSED)
REFILL_COUNT = int(config.CHITCHAT_REFILL_COUNT)

# 口語パーツ。きれいにまとめない。家計・洗剤・ストックの話は入れない。
_SCENES: Sequence[str] = (
    "朝起きたらスマホの充電ほぼゼロで",
    "電車で隣の人の動画音漏れてて",
    "エレベーター来なくて結局階段で",
    "コンビニでアイス選んでる時間長すぎて",
    "信号待ちのあいだに予定全部思い出して",
    "寝癖が右側だけ絶対立ってて",
    "リモコンまたソファの隙間に落として",
    "キーボードの隙間のパンくず気になって",
    "会社のエアコン当たりすぎて",
    "雨の日の電車の匂い嗅いだら",
    "土曜日の午後、気づいたら2時間寝てて",
    "雲がなんか動物に見えて時間溶けて",
    "靴の左だけすぐ痛くて",
    "通知オフにしたアプリのバッジだけ残ってて",
    "朝は涼しくて長袖着たら昼で後悔して",
    "蝉の声フルボリュームで起きて",
    "メール返そうとして別アプリ開いて",
    "レジ列、隣の方が早く減ってて",
    "バナナ買った翌日にもう斑点出てて",
    "立ち上がったら膝だけ元気な音して",
    "リビング来たのに用忘れて",
    "通勤プレイリスト選んでるうちに駅着いて",
    "昨夜の夢が意味不明すぎて",
    "インスタント味噌汁飲んで朝始まって",
)

_MID: Sequence[str] = (
    "ちょっと笑った",
    "地味にイラッとした",
    "自分でもどうでもいいと思ってる",
    "誰かに言いたくなった",
    "年齢を感じた…のか忙しかっただけか",
    "もう慣れすぎてる",
    "朝からテンション下がった",
    "逆にスッキリした",
)

_ENDS: Sequence[str] = (
    "わかる人いる？",
    "うちだけ？",
    "同じのいる？",
    "気になる人いる？",
    "あるあるすぎる…",
    "最近どう？",
    "似たこと、ない？",
)


def _now_stamp() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def load_pool(path: Path | None = None) -> dict[str, Any]:
    p = path or Path(CHITCHAT_POOL_PATH)
    if not p.exists():
        return {"updated_at": "", "items": []}
    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {"updated_at": "", "items": []}
    items = raw.get("items") or []
    if not isinstance(items, list):
        items = []
    return {"updated_at": str(raw.get("updated_at") or ""), "items": items}


def save_pool(payload: dict[str, Any], path: Path | None = None) -> None:
    p = path or Path(CHITCHAT_POOL_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload["updated_at"] = _now_stamp()
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _existing_ids(items: list[dict[str, Any]]) -> set[str]:
    return {str(i.get("id") or "") for i in items if str(i.get("id") or "")}


def _make_id(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"chat-auto-{digest}"


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def generate_via_fragments(n: int, *, existing: set[str] | None = None) -> List[dict[str, Any]]:
    """APIなしで口語雑談を組み合わせ生成。"""
    existing = set(existing or ())
    out: List[dict[str, Any]] = []
    # 決定的すぎないが、同じ実行で重複しにくいようシャッフル
    scenes = list(_SCENES)
    mids = list(_MID)
    ends = list(_ENDS)
    random.shuffle(scenes)
    random.shuffle(mids)
    random.shuffle(ends)
    attempts = 0
    i_s = i_m = i_e = 0
    while len(out) < n and attempts < n * 20:
        attempts += 1
        scene = scenes[i_s % len(scenes)]
        mid = mids[i_m % len(mids)]
        end = ends[i_e % len(ends)]
        i_s += 1
        i_m += 1
        if attempts % 3 == 0:
            i_e += 1
        text = _normalize_text(f"{scene}\n\n{mid}\n\n{end}")
        vid = _make_id(text)
        if vid in existing:
            # 少し揺らす
            text = _normalize_text(f"{scene}\n{mid}…\n\n{end}")
            vid = _make_id(text)
        if vid in existing:
            continue
        existing.add(vid)
        out.append(
            {
                "id": vid,
                "text": text,
                "source": "auto-fragment",
                "created_at": _now_stamp(),
            }
        )
    return out


def generate_via_llm(n: int, *, existing: set[str] | None = None) -> List[dict[str, Any]]:
    """OpenAI互換APIで雑談下書きを生成。失敗時は空リスト。"""
    import httpx

    api_key = (
        os.environ.get("CHITCHAT_LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    ).strip()
    if not api_key:
        return []
    base = (
        os.environ.get("CHITCHAT_LLM_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    model = os.environ.get("CHITCHAT_LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"

    system = (
        "あなたは日本人の普通のSNSユーザーです。"
        "どうでもいい短い雑談を日本語で書いてください。"
        "禁止: 日用品・洗剤・ポイント・楽天・節約術・共働き家事のノウハウ・きれいなまとめ・広告っぽい文章。"
        "口語で、友達に送る愚痴くらいの崩し方。"
        "1投稿は2〜5短文。最後は軽い問いかけか独り言。"
        "出力はJSON配列のみ。各要素は {\"text\": \"...\"}。"
    )
    user = (
        f"{n}本、内容が被らない雑談を作って。"
        "例の雰囲気:\n"
        "朝起きたらスマホ12%で焦った\\n\\n"
        "寝る前充電したつもりだったんだけど\\n"
        "ケーブル挿したフリして寝てたらしい\\n\\n"
        "あるあるすぎる…"
    )
    with httpx.Client(timeout=60.0) as client:
        res = client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": 0.95,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        res.raise_for_status()
        content = res.json()["choices"][0]["message"]["content"]
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    data = json.loads(content)
    if not isinstance(data, list):
        return []
    existing = set(existing or ())
    out: List[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        text = _normalize_text(str(row.get("text") or ""))
        if len(text) < 12:
            continue
        vid = _make_id(text)
        if vid in existing:
            continue
        existing.add(vid)
        out.append(
            {
                "id": vid,
                "text": text,
                "source": "auto-llm",
                "created_at": _now_stamp(),
            }
        )
        if len(out) >= n:
            break
    return out


def generate_chitchat_posts(n: int, *, existing: set[str] | None = None) -> List[dict[str, Any]]:
    existing = set(existing or ())
    posts = generate_via_llm(n, existing=existing)
    if len(posts) < n:
        posts.extend(generate_via_fragments(n - len(posts), existing=existing | {p["id"] for p in posts}))
    return posts[:n]


def ensure_chitchat_supply(
    *,
    min_unused: int | None = None,
    refill_count: int | None = None,
    path: Path | None = None,
) -> int:
    """未使用雑談が足りなければ自動追加。追加件数を返す。"""
    from value_posts import unused_chitchat_posts

    min_unused = MIN_UNUSED if min_unused is None else min_unused
    refill_count = REFILL_COUNT if refill_count is None else refill_count
    path = path or Path(CHITCHAT_POOL_PATH)

    unused_n = len(unused_chitchat_posts())
    if unused_n >= min_unused:
        return 0

    payload = load_pool(path)
    items = list(payload.get("items") or [])
    existing = _existing_ids(items)
    need = max(refill_count, min_unused - unused_n)
    fresh = generate_chitchat_posts(need, existing=existing)
    if not fresh:
        return 0
    items.extend(fresh)
    payload["items"] = items
    save_pool(payload, path)
    print(f"chitchat refill: +{len(fresh)} (unused was {unused_n})", flush=True)
    return len(fresh)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="雑談プールを補充する")
    parser.add_argument("--min-unused", type=int, default=MIN_UNUSED)
    parser.add_argument("--count", type=int, default=REFILL_COUNT)
    args = parser.parse_args()
    n = ensure_chitchat_supply(min_unused=args.min_unused, refill_count=args.count)
    print(f"added={n} path={CHITCHAT_POOL_PATH}")
