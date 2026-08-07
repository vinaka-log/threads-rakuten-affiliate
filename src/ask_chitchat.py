"""問いかけ型雑談（アイス投稿と同系統）の生成・プール。

伸びた型:
  短い季節/話題フック → みんなのオススメ募集 → 自分の回答(しろくま)

通常の chitchat_pool とは別。日用品・商品紹介は禁止。
絵文字は軽く残してよい（ヒット投稿に合わせて）。
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

import config

JST = timezone(timedelta(hours=9))

ASK_POOL_PATH = getattr(config, "ASK_CHITCHAT_POOL_PATH", config.DATA_DIR / "ask_chitchat_pool.json")
TREND_SEEDS_PATH = getattr(config, "TREND_SEEDS_PATH", config.DATA_DIR / "trend_seeds.json")
MIN_UNUSED = int(getattr(config, "ASK_CHITCHAT_MIN_UNUSED", 6))
REFILL_COUNT = int(getattr(config, "ASK_CHITCHAT_REFILL_COUNT", 10))

# 月別の季節ネタ (topic, emoji, my_answer)
_SEASONAL: dict[int, Sequence[Tuple[str, str, str]]] = {
    1: (
        ("おでんの具", "🍢", "大根一択"),
        ("冬の飲み物", "☕", "ホットミルクティー"),
        ("こたつで食べるもの", "🍊", "みかん"),
    ),
    2: (
        ("バレンタインのお返し", "🎁", "特に何も期待してない"),
        ("冬の夜食", "🍜", "カップ麺"),
        ("節分の恵方巻き", "🍣", "普通に切って食べる派"),
    ),
    3: (
        ("桜より先に思い浮かぶ春のもの", "🌸", "花粉症…"),
        ("新生活で買うもの", "🎒", "とりあえずティッシュ"),
        ("春のおやつ", "🍓", "いちご狩りしたい気持ち"),
    ),
    4: (
        ("お花見のお供", "🍡", "だんご"),
        ("春のコンビニスイーツ", "🧁", "その場の衝動買い"),
        ("GWの過ごし方", "🏠", "家でゴロゴロ"),
    ),
    5: (
        ("初夏の匂い", "🌿", "雨上がりのアスファルト"),
        ("こどもの日といえば", "🎏", "かしわもち"),
        ("梅雨入り前にやりたいこと", "☀️", "布団干し"),
    ),
    6: (
        ("梅雨のストレス発散", "☔", "ホットケーキ"),
        ("あじさいより好きな紫", "", "ぶどうジュース"),
        ("湿気との戦い方", "🌀", "風呂上がりすぐエアコン"),
    ),
    7: (
        ("夏といえばアイス", "🍨", "しろくまくん"),
        ("かき氷の味", "🍧", "いちご一択"),
        ("夏の飲み物", "", "麦茶一択"),
        ("花火より好きな夏の夜の過ごし方", "🎆", "アイス食べながら動画"),
    ),
    8: (
        ("夏といえばアイス", "🍨", "しろくまくん"),
        ("かき氷の味", "🍧", "いちご一択"),
        ("夏の飲み物", "", "麦茶一択"),
        ("スイカの食べ方", "🍉", "塩かけて食べる派"),
        ("夏休みの思い出おやつ", "🍦", "やっぱりアイス"),
        ("夏の夜のコンビニ", "🏪", "アイス売り場で長居"),
    ),
    9: (
        ("秋といえば食欲", "🍂", "焼き芋"),
        ("敬老の日のお土産候補", "🎁", "お茶セット無難説"),
        ("残暑のアイス", "🍨", "まだしろくまくん引退できない"),
    ),
    10: (
        ("秋の味覚", "🍠", "焼き芋一択"),
        ("ハロウィンのお菓子", "🎃", "そのまま自分で食べる"),
        ("秋の夜長に見たいもの", "📺", "サスペンス"),
    ),
    11: (
        ("鍋の具材", "🍲", "白菜と豚肉"),
        ("秋冬のコンビニホットスナック", "🍟", "フライドチキン"),
        ("年末に向けてやめたい癖", "", "スヌーズ連打"),
    ),
    12: (
        ("冬といえばこれ", "❄️", "こたつみかん"),
        ("年越しそば派？うどん派？", "🍜", "そば"),
        ("クリスマスより大事な冬の楽しみ", "🎄", "イルミネーション見て帰る"),
    ),
}

# トレンド/ニュースっぽいが重くない話題（RSS失敗時の保険）
_EVERGREEN_TRENDS: Sequence[Tuple[str, str, str]] = (
    ("最近の朝ドラ", "📺", "途中から追いつきたい派"),
    ("今季のアニメ", "✨", "まだ何見るか迷ってる"),
        ("プロ野球、今年の注目", "⚾", "しばらく見てるだけ"),
    ("台風くる前にやること", "🌀", "とりあえず入浴剤買う"),
    ("新作ポテトチップス", "🥔", "一回は試す"),
    ("今のスマホケース流行り", "📱", "クリア派から動けない"),
    ("最近のコンビニ新作", "🏪", "見た瞬間カゴに入れがち"),
    ("今バズってる曲", "🎵", "サビだけ知ってる"),
    ("SNSの新機能", "📱", "使い方わかる人教えて"),
    ("今の天気予報アプリ", "🌦️", "標準のままで十分派"),
)


def _now_stamp() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def _today() -> datetime:
    return datetime.now(JST)


def load_pool(path: Path | None = None) -> dict[str, Any]:
    p = path or Path(ASK_POOL_PATH)
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
    p = path or Path(ASK_POOL_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload["updated_at"] = _now_stamp()
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_trend_seeds(path: Path | None = None) -> list[str]:
    p = path or Path(TREND_SEEDS_PATH)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(raw, dict):
        seeds = raw.get("seeds") or []
    elif isinstance(raw, list):
        seeds = raw
    else:
        return []
    return [str(s).strip() for s in seeds if str(s).strip()]


def save_trend_seeds(seeds: list[str], path: Path | None = None) -> None:
    p = path or Path(TREND_SEEDS_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": _now_stamp(), "seeds": seeds[:30]}
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _make_id(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"ask-{digest}"


def _normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _render_ask(topic: str, emoji: str, answer: str) -> str:
    emo = f"{emoji} " if emoji else ""
    patterns = [
        f"{topic}だよね{emo}みんなのオススメ教えて〜 僕は{answer}🐻‍❄️",
        f"{topic}、みんな何派？教えて〜 僕は{answer}🐻‍❄️",
        f"最近気になってるんだけど、{topic}のおすすめ教えて〜 僕は{answer}🐻‍❄️",
        f"{topic}といえば？みんなの推しください 僕は{answer}、しろくまも賛成🐻‍❄️",
    ]
    return _normalize(random.choice(patterns))


def _soften_trend_topic(seed: str) -> str:
    """長い見出しを問いかけ向けの短い話題に落とす。"""
    raw = seed.strip("。．!！?？ \n「」『』")
    seed = re.sub(r"^【[^】]*】", "", raw).strip()
    if "プロ野球結果" in raw or ("プロ野球" in raw and ("勝ち" in seed or "敗" in seed)):
        return "今日のプロ野球"
    if "大谷" in raw:
        return "大谷選手の近況"
    if "ピッチクロック" in raw:
        return "プロ野球のピッチクロック"
    if "Jリーグ" in raw or ("サッカー" in raw and "開幕" in raw):
        return "今のサッカー開幕ムード"
    if "五輪" in raw:
        return "五輪まわりの話題"
    if "バレー" in raw:
        return "最近のバレー日本代表"
    if "バスケ" in raw or "八村" in raw:
        return "バスケ日本代表"
    if "猛暑" in raw or "酷暑" in raw or "熱中症" in raw or "暑熱" in raw:
        return "今年の暑さ対策"
    if "ラベルレス" in raw:
        return "ラベルレスの水・飲料"
    if "コンビニ" in raw:
        return "最近のコンビニ新作"
    if "殿堂" in raw and "サッカー" in raw:
        return "サッカー殿堂入りの話題"
    # スポーツ結果は種目名に寄せる（テンプレ側に「最近」があるので先頭に付けない）
    for key, label in (
        ("プロ野球", "プロ野球"),
        ("サッカー", "サッカー"),
        ("バスケ", "バスケ"),
        ("バレー", "バレー日本代表"),
    ):
        if key in raw:
            return label
    if len(seed) > 18:
        seed = seed[:17] + "…"
    return seed or "今のニュース"


def _render_trend_ask(seed: str) -> str:
    topic = _soften_trend_topic(seed)
    patterns = [
        f"最近『{topic}』が気になるんだけど、みんなの感想教えて〜 僕はまだふわっとしか知らない🐻‍❄️",
        f"『{topic}』、キャッチアップできてる人いる？推しポイント教えて〜 しろくまは様子見中🐻‍❄️",
        f"今っぽい話だけど『{topic}』、気になってる人〜？みんなはどう思う？🐻‍❄️",
    ]
    return _normalize(random.choice(patterns))


# 重いニュースはアカウントのトーンに合わないので除外。
_TREND_BLOCK = (
    "死亡",
    "殺人",
    "事故死",
    "戦争",
    "爆撃",
    "津波",
    "震災",
    "地震",
    "爆発",
    "殺害",
    "犠牲",
    "被災",
    "避難",
    "火災",
    "火事",
    "人権侵害",
    "介入",
    "減税",
    "自民",
    "首相",
    "閣議",
    "攻撃",
    "過激",
    "容疑",
    "逮捕",
    "裁判",
    "訃報",
    "死去",
    "死ぬ",
    "遺族",
)

# 軽い話題だけ拾う（スポーツ・季節・生活・エンタメ寄り）。
_TREND_ALLOW = (
    "プロ野球",
    "サッカー",
    "バスケ",
    "バレー",
    "大谷",
    "侍ジャパン",
    "Jリーグ",
    "五輪",
    "猛暑",
    "酷暑",
    "熱中症",
    "台風",
    "ラベルレス",
    "コンビニ",
    "アニメ",
    "映画",
    "ドラマ",
    "朝ドラ",
    "ミュージック",
    "音楽",
    "フェス",
    "新作",
    "発売",
    "グルメ",
    "アイス",
    "かき氷",
    "夏",
    "花火",
    "祭り",
    "動物園",
    "水族館",
    "宇宙",
    "JAXA",
    "はやぶさ",
)


def fetch_trend_seeds_from_rss(*, limit: int = 12) -> list[str]:
    """軽いニュース見出しをRSSから取得（失敗したら空）。

    主要ニュースは事故・政治が混ざりやすいので、スポーツ優先 + allow単語フィルタ。
    """
    import httpx

    feeds = (
        "https://www.nhk.or.jp/rss/news/cat7.xml",  # スポーツ
        "https://www.nhk.or.jp/rss/news/cat2.xml",  # 文化・エンタメ（混在あり）
        "https://www.nhk.or.jp/rss/news/cat3.xml",  # 科学・医療（軽い科学ネタ）
        "https://www.nhk.or.jp/rss/news/cat0.xml",  # 主要（allowのみ）
    )
    titles: list[str] = []
    try:
        with httpx.Client(timeout=12.0, follow_redirects=True) as client:
            for url in feeds:
                try:
                    res = client.get(url)
                    res.raise_for_status()
                except Exception:
                    continue
                for m in re.finditer(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", res.text):
                    t = m.group(1).strip()
                    if not t or t.startswith("NHK") or "主要ニュース" in t:
                        continue
                    if any(b in t for b in _TREND_BLOCK):
                        continue
                    if not any(a in t for a in _TREND_ALLOW):
                        continue
                    if t not in titles:
                        titles.append(t)
                    if len(titles) >= limit:
                        return titles
    except Exception:
        return titles
    return titles


def refresh_trend_seeds() -> list[str]:
    seeds = fetch_trend_seeds_from_rss()
    if seeds:
        save_trend_seeds(seeds)
    return seeds or load_trend_seeds()


def _topic_candidates(now: Optional[datetime] = None) -> list[Tuple[str, str, str]]:
    now = now or _today()
    month = now.month
    out: list[Tuple[str, str, str]] = []
    out.extend(list(_SEASONAL.get(month, ())))
    out.extend(list(_SEASONAL.get(month % 12 + 1, ()))[:2])
    out.extend(list(_EVERGREEN_TRENDS))
    random.shuffle(out)
    return out


def _generate_ask_via_llm(
    n: int,
    *,
    existing_ids: set[str],
    trend_seeds: Sequence[str],
) -> List[dict[str, Any]]:
    import httpx

    api_key = (
        os.environ.get("CHITCHAT_LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    ).strip()
    if not api_key or n <= 0:
        return []
    base = (
        os.environ.get("CHITCHAT_LLM_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    model = os.environ.get("CHITCHAT_LLM_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    month = _today().strftime("%Y年%m月")
    trends = " / ".join(trend_seeds) if trend_seeds else "（特になし）"
    system = (
        "日本人の普通のThreadsユーザーとして、短い問いかけ投稿を書いてください。"
        "型: 話題フック → みんなのオススメ/感想を聞く → 自分の答え（しろくま/🐻‍❄️ を自然に）。"
        "1投稿は1〜3行。売り込み・楽天・日用品・ポイント・節約術は禁止。"
        "重い政治・事件・事故のネタは禁止。季節と軽いトレンド中心。"
        "絵文字は0〜2個まで。ハッシュタグ禁止。"
        "出力はJSON配列のみ。各要素は {\"text\": \"...\"}。"
    )
    user = (
        f"{n}本作って。いまは{month}。参考トレンド見出し: {trends}\n"
        "例: 夏といえばアイスだよね🍨 みんなのオススメアイスを教えて〜 僕はしろくまくん Polar"
    ).replace(" Polar", "🐻‍❄️")
    try:
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
            content = res.json()["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        print(f"WARNING: ask llm failed: {exc}", flush=True)
        return []
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        data = json.loads(content)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: List[dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        text = _normalize(str(row.get("text") or ""))
        if len(text) < 10:
            continue
        vid = _make_id(text)
        if vid in existing_ids:
            continue
        existing_ids.add(vid)
        out.append(
            {
                "id": vid,
                "text": text,
                "source": "ask-llm",
                "created_at": _now_stamp(),
            }
        )
        if len(out) >= n:
            break
    return out


def generate_ask_posts(n: int, *, existing_ids: set[str] | None = None) -> List[dict[str, Any]]:
    existing_ids = set(existing_ids or ())
    seen_text: set[str] = set()
    out: List[dict[str, Any]] = []

    seeds = load_trend_seeds() or refresh_trend_seeds()
    random.shuffle(seeds)
    for seed in seeds:
        if len(out) >= max(1, n // 2):
            break
        text = _render_trend_ask(seed)
        vid = _make_id(text)
        if vid in existing_ids or text in seen_text:
            continue
        existing_ids.add(vid)
        seen_text.add(text)
        out.append(
            {
                "id": vid,
                "text": text,
                "source": "ask-trend",
                "created_at": _now_stamp(),
            }
        )

    for topic, emoji, answer in _topic_candidates():
        if len(out) >= n:
            break
        text = _render_ask(topic, emoji, answer)
        vid = _make_id(text)
        if vid in existing_ids or text in seen_text:
            continue
        existing_ids.add(vid)
        seen_text.add(text)
        out.append(
            {
                "id": vid,
                "text": text,
                "source": "ask-season",
                "created_at": _now_stamp(),
            }
        )

    if len(out) < n:
        out.extend(
            _generate_ask_via_llm(
                n - len(out),
                existing_ids=existing_ids,
                trend_seeds=seeds[:8],
            )
        )
    return out[:n]


def used_ask_ids(ledger_path: Path | None = None) -> set[str]:
    from picker import load_ledger

    entries = load_ledger(ledger_path or config.LEDGER_PATH)
    used: set[str] = set()
    for e in entries:
        code = str(e.get("item_code") or "")
        if not code.startswith("value:"):
            continue
        vid = code.split(":", 1)[1]
        kind = str(e.get("kind") or "")
        # 問いかけ枠と旧夏ワンショットのみ（通常 chitchat は別プール）
        if vid.startswith("ask-") or vid.startswith("chat-summer-") or kind == "ask-chitchat":
            used.add(vid)
    return used


def unused_ask_posts() -> list[dict[str, Any]]:
    payload = load_pool()
    used = used_ask_ids()
    out = []
    for row in payload.get("items") or []:
        if not isinstance(row, dict):
            continue
        vid = str(row.get("id") or "")
        text = str(row.get("text") or "").strip()
        if not vid or not text or vid in used:
            continue
        out.append(row)
    return out


def ensure_ask_supply(
    *,
    min_unused: int | None = None,
    refill_count: int | None = None,
    refresh_trends: bool = True,
) -> int:
    min_unused = MIN_UNUSED if min_unused is None else min_unused
    refill_count = REFILL_COUNT if refill_count is None else refill_count
    if refresh_trends:
        try:
            refresh_trend_seeds()
        except Exception as exc:
            print(f"WARNING: trend refresh failed: {exc}", flush=True)

    unused_n = len(unused_ask_posts())
    if unused_n >= min_unused:
        return 0

    payload = load_pool()
    items = list(payload.get("items") or [])
    existing = {str(i.get("id") or "") for i in items if isinstance(i, dict)}
    need = max(refill_count, min_unused - unused_n)
    fresh = generate_ask_posts(need * 2, existing_ids=existing)
    added = 0
    seen_text = {_normalize(str(i.get("text") or "")) for i in items if isinstance(i, dict)}
    for row in fresh:
        t = _normalize(str(row.get("text") or ""))
        if not t or t in seen_text:
            continue
        seen_text.add(t)
        vid = _make_id(t)
        if vid in existing:
            continue
        existing.add(vid)
        items.append({**row, "id": vid, "text": t})
        added += 1
        if added >= need:
            break
    if added:
        payload["items"] = items
        save_pool(payload)
        print(f"ask-chitchat refill: +{added} (unused was {unused_n})", flush=True)
    return added


def pick_ask_post(*, slot_salt: int = 0) -> dict[str, Any]:
    ensure_ask_supply()
    unused = unused_ask_posts()
    if not unused:
        raise RuntimeError("ask-chitchat pool is empty")
    day = _today().toordinal()
    idx = (day * 5 + int(slot_salt)) % len(unused)
    return unused[idx]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="問いかけ型雑談プールを補充")
    parser.add_argument("--min-unused", type=int, default=MIN_UNUSED)
    parser.add_argument("--count", type=int, default=REFILL_COUNT)
    parser.add_argument("--refresh-trends", action="store_true")
    args = parser.parse_args()
    if args.refresh_trends:
        seeds = refresh_trend_seeds()
        print(f"trend_seeds={len(seeds)}")
    n = ensure_ask_supply(min_unused=args.min_unused, refill_count=args.count)
    print(f"added={n} path={ASK_POOL_PATH}")
