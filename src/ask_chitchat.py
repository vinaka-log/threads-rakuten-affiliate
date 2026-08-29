"""Threads公式4択アンケート用の問いかけプール。

型:
  短い質問テキスト + option_a..d（各1〜25字）

通常の chitchat_pool とは別。ベビー商品紹介・PRは禁止。
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
POLL_OPTION_MAX = 25

# (question, (opt_a, opt_b, opt_c, opt_d))
_SEASONAL_POLLS: dict[int, Sequence[Tuple[str, Tuple[str, str, str, str]]]] = {
    1: (
        ("おでんの具、いちばん好きなのは？", ("大根", "卵", "はんぺん", "その他")),
        ("冬の飲み物、何派？", ("ホットミルクティー", "ココア", "カフェラテ", "その他")),
        ("こたつで食べるものといえば？", ("みかん", "アイスクリーム", "おもち", "その他")),
    ),
    2: (
        ("バレンタインのお返し、どうする？", ("お返しする", "特になし", "義理だけ", "まだ迷ってる")),
        ("冬の夜食、何食べる？", ("カップ麺", "おにぎり", "アイス", "食べない")),
        ("恵方巻き、どう食べる？", ("丸かぶり", "切って食べる", "買わない", "その他")),
    ),
    3: (
        ("春といえば、先に思い浮かぶのは？", ("桜", "花粉症", "新生活", "いちご")),
        ("新生活で先に買うものある？", ("ティッシュ", "洗剤", "ゴミ袋", "まだ何も")),
        ("春のおやつ、推しは？", ("いちごスイーツ", "さくら餅", "どら焼き", "その他")),
    ),
    4: (
        ("お花見のお供、何持っていく？", ("だんご", "お弁当", "コンビニ", "行かない")),
        ("GWの過ごし方、どれに近い？", ("家でゴロゴロ", "旅行", "帰省", "まだ未定")),
        ("春のコンビニスイーツ、買う？", ("衝動買いがち", "計画的に買う", "たまに", "ほぼ買わない")),
    ),
    5: (
        ("こどもの日といえば？", ("かしわもち", "ちまき", "特になし", "その他")),
        ("梅雨入り前にやりたいことある？", ("布団干し", "大掃除", "旅行", "特になし")),
        ("初夏の匂いといえば？", ("雨上がり", "芝生", "日焼け止め", "その他")),
    ),
    6: (
        ("梅雨のストレス発散、何する？", ("ホットケーキ", "昼寝", "買い物", "その他")),
        ("湿気との戦い、どうしてる？", ("すぐエアコン", "除湿機", "我慢", "その他")),
        ("あじさいシーズン、外出する？", ("見る派", "家にいる", "写真だけ", "興味薄い")),
    ),
    7: (
        ("夏といえばアイス、推しは？", ("しろくまくん", "ガリガリ君", "ハーゲンダッツ", "その他")),
        ("かき氷の味、どれ派？", ("いちご", "宇治金時", "レモン", "その他")),
        ("夏の飲み物、いちばん飲むのは？", ("麦茶", "水", "炭酸", "その他")),
        ("夏の夜の過ごし方は？", ("アイス＋動画", "花火", "コンビニ", "早めに寝る")),
    ),
    8: (
        ("夏といえばアイス、推しは？", ("しろくまくん", "ガリガリ君", "ハーゲンダッツ", "その他")),
        ("かき氷の味、どれ派？", ("いちご", "宇治金時", "メロン", "その他")),
        ("夏の飲み物、いちばん飲むのは？", ("麦茶", "水", "炭酸", "その他")),
        ("スイカ、どう食べる？", ("塩かける", "そのまま", "冷凍する", "あまり食べない")),
        ("夏の夜のコンビニ、何買う？", ("アイス", "飲み物", "おやつ", "ほぼ行かない")),
        ("今年の暑さ対策、メインは？", ("麦茶と日陰", "エアコン", "冷感グッズ", "まだ模索中")),
    ),
    9: (
        ("秋といえば食欲、何が食べたい？", ("焼き芋", "さんま", "きのこ", "その他")),
        ("残暑でもアイス食べる？", ("まだ食べる", "もう卒業", "たまに", "季節無関係")),
        ("敬老の日のお土産、何が無難？", ("お茶セット", "お菓子", "花", "まだ決めてない")),
    ),
    10: (
        ("秋の味覚、いちばん好きなのは？", ("焼き芋", "栗", "ぶどう", "その他")),
        ("ハロウィンのお菓子、どうする？", ("自分で食べる", "配る", "買わない", "その他")),
        ("秋の夜長に見たいものは？", ("サスペンス", "アニメ", "バラエティ", "その他")),
    ),
    11: (
        ("鍋の具材、絶対入れるのは？", ("白菜と豚肉", "キムチ", "海鮮", "その他")),
        ("コンビニのホットスナック、推しは？", ("フライドチキン", "肉まん", "中華まん", "その他")),
        ("年末に向けてやめたい癖ある？", ("スヌーズ連打", "夜ふかし", "衝動買い", "特になし")),
    ),
    12: (
        ("冬といえばこれ、どれ派？", ("こたつみかん", "おでん", "鍋", "その他")),
        ("年越しはそば？うどん？", ("そば", "うどん", "どっちも", "まだ決めてない")),
        ("クリスマスより大事な冬の楽しみは？", ("イルミネーション", "帰省", "鍋パーティー", "その他")),
    ),
}

_EVERGREEN_POLLS: Sequence[Tuple[str, Tuple[str, str, str, str]]] = (
    ("最近の朝ドラ、見てる？", ("毎日見てる", "追いつきたい", "途中離脱", "見てない")),
    ("今季のアニメ、何見る？", ("もう決めた", "迷ってる", "まだ見てない", "アニメ見ない")),
    ("プロ野球、今年の推しある？", ("ある", "特にない", "たまに見る", "見てない")),
    ("新作ポテチ、試す派？", ("一回は試す", "定番だけ", "見かけたら買う", "興味薄い")),
    ("最近のコンビニ新作、買う？", ("見た瞬間買う", "たまに", "ほぼ買わない", "チェックしない")),
    ("今バズってる曲、知ってる？", ("フルで知ってる", "サビだけ", "名前だけ", "知らない")),
    ("天気予報アプリ、何使ってる？", ("標準のまま", "専用アプリ", "Yahoo系", "あまり見ない")),
    ("SNSの新機能、使いこなせる？", ("すぐ使う", "様子見", "わからない", "興味ない")),
)


def _now_stamp() -> str:
    return datetime.now(JST).isoformat(timespec="seconds")


def _today() -> datetime:
    return datetime.now(JST)


def _clip_option(text: str, limit: int = POLL_OPTION_MAX) -> str:
    text = re.sub(r"\s+", " ", str(text or "").strip())
    if len(text) > limit:
        text = text[:limit]
    return text


def normalize_poll_options(options: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in options:
        opt = _clip_option(raw)
        if not opt or opt in seen:
            continue
        seen.add(opt)
        out.append(opt)
        if len(out) >= 4:
            break
    while len(out) < 4:
        filler = f"その他{len(out)}" if "その他" in seen else "その他"
        filler = _clip_option(filler)
        if filler not in seen:
            seen.add(filler)
            out.append(filler)
        else:
            out.append(_clip_option(f"選択肢{len(out)+1}"))
    return out[:4]


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


def _make_id(text: str, options: Sequence[str]) -> str:
    digest = hashlib.sha1(f"{text}|{'|'.join(options)}".encode("utf-8")).hexdigest()[:10]
    return f"ask-{digest}"


def _normalize_question(text: str) -> str:
    text = text.replace("\r\n", "\n").strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _soften_trend_topic(seed: str) -> str:
    raw = seed.strip("。．!！?？ \n「」『』")
    seed = re.sub(r"^【[^】]*】", "", raw).strip()
    if "プロ野球結果" in raw or ("プロ野球" in raw and ("勝ち" in seed or "敗" in seed)):
        return "今日のプロ野球"
    if "大谷" in raw:
        return "大谷選手の近況"
    if "ピッチクロック" in raw:
        return "プロ野球のピッチクロック"
    if "Jリーグ" in raw or ("サッカー" in raw and "開幕" in raw):
        return "今のサッカー"
    if "五輪" in raw:
        return "五輪まわり"
    if "バレー" in raw:
        return "バレー日本代表"
    if "バスケ" in raw or "八村" in raw:
        return "バスケ日本代表"
    if "猛暑" in raw or "酷暑" in raw or "熱中症" in raw or "暑熱" in raw:
        return "今年の暑さ対策"
    if "ラベルレス" in raw:
        return "ラベルレス飲料"
    if "コンビニ" in raw:
        return "コンビニ新作"
    if "殿堂" in raw and "サッカー" in raw:
        return "サッカー殿堂入り"
    for key, label in (
        ("プロ野球", "プロ野球"),
        ("サッカー", "サッカー"),
        ("バスケ", "バスケ"),
        ("バレー", "バレー"),
    ):
        if key in raw:
            return label
    if len(seed) > 18:
        seed = seed[:17] + "…"
    return seed or "今のニュース"


_TREND_BLOCK = (
    "死亡", "殺人", "事故死", "戦争", "爆撃", "津波", "震災", "地震", "爆発", "殺害",
    "犠牲", "被災", "避難", "火災", "火事", "人権侵害", "介入", "減税", "自民", "首相",
    "閣議", "攻撃", "過激", "容疑", "逮捕", "裁判", "訃報", "死去", "死ぬ", "遺族",
)
_TREND_ALLOW = (
    "プロ野球", "サッカー", "バスケ", "バレー", "大谷", "侍ジャパン", "Jリーグ", "五輪",
    "猛暑", "酷暑", "熱中症", "台風", "ラベルレス", "コンビニ", "アニメ", "映画", "ドラマ",
    "朝ドラ", "ミュージック", "音楽", "フェス", "新作", "発売", "グルメ", "アイス",
    "かき氷", "夏", "花火", "祭り", "動物園", "水族館", "宇宙", "JAXA", "はやぶさ",
)


def fetch_trend_seeds_from_rss(*, limit: int = 12) -> list[str]:
    import httpx

    feeds = (
        "https://www.nhk.or.jp/rss/news/cat7.xml",
        "https://www.nhk.or.jp/rss/news/cat2.xml",
        "https://www.nhk.or.jp/rss/news/cat3.xml",
        "https://www.nhk.or.jp/rss/news/cat0.xml",
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


def _render_poll(question: str, options: Sequence[str]) -> dict[str, Any]:
    text = _normalize_question(question)
    opts = normalize_poll_options(options)
    return {
        "id": _make_id(text, opts),
        "text": text,
        "options": opts,
        "source": "ask-poll",
        "created_at": _now_stamp(),
    }


def _render_trend_poll(seed: str) -> dict[str, Any]:
    topic = _soften_trend_topic(seed)
    question = random.choice(
        (
            f"『{topic}』、みんなどう思う？",
            f"『{topic}』、キャッチアップできてる？",
            f"今っぽい話だけど『{topic}』、気になる？",
        )
    )
    options = ("めっちゃ気になる", "ちょっと気になる", "まだよく知らない", "興味ない")
    row = _render_poll(question, options)
    row["source"] = "ask-trend-poll"
    return row


def _topic_candidates(now: Optional[datetime] = None) -> list[Tuple[str, Tuple[str, str, str, str]]]:
    now = now or _today()
    month = now.month
    out: list[Tuple[str, Tuple[str, str, str, str]]] = []
    out.extend(list(_SEASONAL_POLLS.get(month, ())))
    out.extend(list(_SEASONAL_POLLS.get(month % 12 + 1, ()))[:2])
    out.extend(list(_EVERGREEN_POLLS))
    random.shuffle(out)
    return out


def _generate_poll_via_llm(
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
        "日本人の普通のThreadsユーザーとして、公式4択アンケート投稿を作ってください。"
        "各要素は {\"text\": \"質問\", \"options\": [\"A\",\"B\",\"C\",\"D\"]}。"
        "textは1〜2行の短い質問。optionsは必ず4つ、各1〜25文字。"
        "売り込み・楽天・日用品PR・ハッシュタグ禁止。重い政治・事件禁止。"
        "出力はJSON配列のみ。"
    )
    user = f"{n}本作って。いまは{month}。参考トレンド: {trends}"
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
        print(f"WARNING: ask poll llm failed: {exc}", flush=True)
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
        text = _normalize_question(str(row.get("text") or ""))
        opts = normalize_poll_options(row.get("options") or [])
        if len(text) < 6 or len(opts) != 4:
            continue
        vid = _make_id(text, opts)
        if vid in existing_ids:
            continue
        existing_ids.add(vid)
        out.append(
            {
                "id": vid,
                "text": text,
                "options": opts,
                "source": "ask-poll-llm",
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
        if len(out) >= max(1, n // 3):
            break
        row = _render_trend_poll(seed)
        if row["id"] in existing_ids or row["text"] in seen_text:
            continue
        existing_ids.add(row["id"])
        seen_text.add(row["text"])
        out.append(row)

    for question, options in _topic_candidates():
        if len(out) >= n:
            break
        row = _render_poll(question, options)
        row["source"] = "ask-season-poll"
        if row["id"] in existing_ids or row["text"] in seen_text:
            continue
        existing_ids.add(row["id"])
        seen_text.add(row["text"])
        out.append(row)

    if len(out) < n:
        out.extend(
            _generate_poll_via_llm(
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
        opts = normalize_poll_options(row.get("options") or [])
        if not vid or not text or vid in used:
            continue
        # 旧テキスト専用シードは選択肢を補完して使えるようにする
        out.append({**row, "text": text, "options": opts})
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
    seen_text = {_normalize_question(str(i.get("text") or "")) for i in items if isinstance(i, dict)}
    for row in fresh:
        t = _normalize_question(str(row.get("text") or ""))
        opts = normalize_poll_options(row.get("options") or [])
        if not t or t in seen_text or len(opts) != 4:
            continue
        seen_text.add(t)
        vid = _make_id(t, opts)
        if vid in existing:
            continue
        existing.add(vid)
        items.append({**row, "id": vid, "text": t, "options": opts})
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
    row = unused[idx]
    return {
        **row,
        "options": normalize_poll_options(row.get("options") or []),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="公式4択アンケートプールを補充")
    parser.add_argument("--min-unused", type=int, default=MIN_UNUSED)
    parser.add_argument("--count", type=int, default=REFILL_COUNT)
    parser.add_argument("--refresh-trends", action="store_true")
    args = parser.parse_args()
    if args.refresh_trends:
        seeds = refresh_trend_seeds()
        print(f"trend_seeds={len(seeds)}")
    n = ensure_ask_supply(min_unused=args.min_unused, refill_count=args.count)
    print(f"added={n} path={ASK_POOL_PATH}")
