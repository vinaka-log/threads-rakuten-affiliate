"""Threads × 楽天アフィリエイト 自動投稿の設定。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# リポジトリルート
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
LEDGER_PATH = DATA_DIR / "posted.json"

# Threads 投稿の文字数上限（余裕を持って短めに）
MAX_TEXT_LEN = 480

# 同一 itemCode の再投稿禁止日数
DEDUP_DAYS = 30

# 紹介品質フィルタ
MIN_REVIEW_AVERAGE = 4.0
MIN_REVIEW_COUNT = 100

# ランキング取得件数（上位からフィルタ）
RANKING_HITS = 30


@dataclass(frozen=True)
class Genre:
    id: str
    label: str
    # 投稿文で使う短いカテゴリ名
    short: str


# 総合ランキング + 日用品系（後から差し替え可）
# genreId "0" = 総合
GENRES: List[Genre] = [
    Genre(id="0", label="総合ランキング", short="売れ筋"),
    Genre(id="100939", label="日用品・文房具・手芸", short="日用品"),
    Genre(id="100227", label="水・ソフトドリンク", short="ドリンク"),
    Genre(id="551167", label="キッチン用品・食器・調理器具", short="キッチン"),
]

# 日内枠（JST）: slot → (時刻ラベル, GENRES インデックスのオフセット)
# 日付×slot でジャンルをローテ
SLOT_LABELS: Tuple[str, ...] = (
    "08:00",
    "12:00",
    "20:00",
)
POSTS_PER_DAY = len(SLOT_LABELS)

# 楽天 API エンドポイント（2025年以降の新仕様）
RAKUTEN_RANKING_URL = (
    "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
)
RAKUTEN_SEARCH_URL = (
    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601"
)
