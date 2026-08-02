"""どうでもいい雑談の自動生成・補充。

方針:
  - 雑談は一度きり（台帳で消費）。足りなくなったらここで足す
  - 既定は「完成文のストック」から未使用を引く（3段テンプレ結合はしない＝AI臭さ回避）
  - OPENAI_API_KEY / CHITCHAT_LLM_API_KEY があれば LLM で下書き生成
  - 絵文字は基本なし。LLMでも控えめに指示
  - 日用品・共働き家事ノウハウには寄せない
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

# 完成した口語メモ。テンプレ結合せず、このまま出す／軽く揺らす。
_DRAFTS: Sequence[str] = (
    "充電したつもりで寝たのに朝ほぼゼロ\n自分で自分を裏切ってる",
    "エレベーター待ってたら結局階段の方が早かった\nいつものことなのに待つ",
    "レジ、隣の列だけ進むの何\n呪いだと思ってる",
    "バナナ、黄色いの選んでも翌日斑点\n急がないでほしい",
    "通勤の曲選びで駅着いた\n結局いつもの曲なのに",
    "リモコンまた隙間\n探すの疲れた",
    "会社寒すぎて羽織り必須\n外との気温差おかしい",
    "雨の日の電車の匂い、独特\n嫌いじゃないけど朝から強い",
    "寝癖右だけ立つ\n今日も帽子検討中",
    "土曜昼寝したら2時間消えた\nまあいいかってなってる",
    "コンビニの氷、帰宅前に溶けてる\n夏の小さな敗北",
    "メール返そうとして別アプリ開いた\n朝の指、信用できない",
    "蝉うるさい\n夏だなあ",
    "信号長すぎて予定全部思い出してしまった",
    "靴下片っぽ行方不明\n洗濯のたびに消える",
    "キーボードのパンくず気になる\n取りたいけど面倒",
    "雲が犬に見えてぼーっとしてた\n時間溶けた",
    "膝鳴る\n痛くない。音だけ立派",
    "通知オフなのにバッジ残ってる\n気になって開いちゃう",
    "朝長袖、昼で暑い\n服装ミスった",
    "ペットボトル開けたとたんこぼした\n机ぬれてる",
    "スヌーズしすぎてギリギリ出勤コース",
    "折りたたみ傘ない日に限って雨\nカバンの中見たつもりだった",
    "イヤホン片耳切れる\n歩きながら再接続してる",
    "パスワード忘れて再設定→いつものやつだった\n何してたんだろ",
    "昼ごはん決められずいつもの定食\n選ぶのしんどい日",
    "電車でうとうとして乗り過ごしそうになった\n心臓止まった",
    "スマホ落としそうになって無言で握りしめた",
    "自販機、推しの飲み物売り切れ\n隣で妥協した",
    "髪乾かしながらぼーっとして時間溶けた",
    "コンビニの店員さんにありがとう連発してる自分いる",
    "階段の段数数えながら上がってる\nなんのため",
    "エアコンのリモコン電池切れ疑惑\n反応薄い",
    "カフェの席、コンセント空いてなくて地味に落ち込む",
    "靴紐ほどけてたの、家着いてから気づいた",
    "切手貼る向き、毎回迷う",
    "メモ帳アプリ開きすぎてどれが本題かわからん",
    "電車の中で眠気と戦いながら既読つけてる",
    "アイス買いすぎた自覚ある\nでも暑い",
    "洗面台の水、止め忘れそうになって振り返った",
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


def _existing_texts(items: list[dict[str, Any]]) -> set[str]:
    return {_normalize_text(str(i.get("text") or "")) for i in items if str(i.get("text") or "").strip()}


def _make_id(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"chat-auto-{digest}"


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 自動生成で絵文字が混ざっても落とす（人間味は文章で出す）
    text = re.sub(
        r"[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F1E0-\U0001F1FF]+",
        "",
        text,
    )
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def _nudge(text: str, salt: int) -> str:
    """ごく軽い揺れ。意味は変えず、同一文の連続生成を避ける。"""
    variants = [
        text,
        text.replace("\n\n", "\n", 1) if "\n\n" in text else text,
        (text + "\nまあいいか") if salt % 7 == 0 and "まあいいか" not in text else text,
        (text + "\nどうでもいい話") if salt % 11 == 0 and "どうでもいい" not in text else text,
    ]
    return _normalize_text(variants[salt % len(variants)])


def generate_via_fragments(n: int, *, existing: set[str] | None = None) -> List[dict[str, Any]]:
    """完成文ストックから未使用を引く（テンプレ結合しない）。"""
    existing_ids = set(existing or ())
    out: List[dict[str, Any]] = []
    drafts = list(_DRAFTS)
    random.shuffle(drafts)
    salt = 0
    # 何周かして nudge でユニーク化
    while len(out) < n and salt < n * 30:
        base = drafts[salt % len(drafts)]
        text = _nudge(base, salt)
        salt += 1
        if not text or len(text) < 8:
            continue
        vid = _make_id(text)
        if vid in existing_ids:
            continue
        existing_ids.add(vid)
        out.append(
            {
                "id": vid,
                "text": text,
                "source": "auto-draft",
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
        "日本人の普通のSNSユーザーとして、どうでもいい短い独り言を書いてください。"
        "AIっぽい整った文章・箇条書き・きれいなまとめ・ハッシュタグは禁止。"
        "絵文字は基本使わない（どうしてもなら😂を稀に1つまで）。"
        "禁止テーマ: 日用品購入、洗剤、ポイント、楽天、節約術、共働き家事ノウハウ、商品紹介。"
        "口語で、友達に送る短いメモくらい崩す。"
        "毎回構造を変える（毎回同じ型の問いかけで終わらせない）。"
        "出力はJSON配列のみ。各要素は {\"text\": \"...\"}。"
    )
    user = (
        f"{n}本、内容が被らない雑談を作って。例:\n"
        "充電したつもりで寝たのに朝12%\\n"
        "ケーブル刺したフリして寝てたっぽい\\n"
        "自分にイライラする"
    )
    with httpx.Client(timeout=60.0) as client:
        res = client.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "temperature": 1.0,
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
    existing_ids = set(existing or ())
    out: List[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        text = _normalize_text(str(row.get("text") or ""))
        if len(text) < 8:
            continue
        vid = _make_id(text)
        if vid in existing_ids:
            continue
        existing_ids.add(vid)
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
        posts.extend(
            generate_via_fragments(n - len(posts), existing=existing | {p["id"] for p in posts})
        )
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
    existing = _existing_ids(items) | {
        _make_id(_normalize_text(str(i.get("text") or ""))) for i in items
    }
    # 本文重複も避ける
    seen_text = _existing_texts(items)
    need = max(refill_count, min_unused - unused_n)
    fresh_raw = generate_chitchat_posts(need * 2, existing=existing)
    fresh: List[dict[str, Any]] = []
    for row in fresh_raw:
        t = _normalize_text(str(row.get("text") or ""))
        if not t or t in seen_text:
            continue
        seen_text.add(t)
        row = dict(row)
        row["text"] = t
        row["id"] = _make_id(t)
        if row["id"] in existing:
            continue
        existing.add(row["id"])
        fresh.append(row)
        if len(fresh) >= need:
            break
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
