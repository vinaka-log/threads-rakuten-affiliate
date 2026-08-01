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

# rank帯ローテ: 日替わりで「上位帯」と「準上位帯」を交互に紹介する。
# 上位帯は競合アカウントと被りやすいため、準上位帯で差別化する。
RANK_BANDS: Tuple[Tuple[int, int], ...] = (
    (1, 10),   # 偶数日: 定番の売れ筋
    (11, 30),  # 奇数日: みんな知らないけど売れてるもの
)

# セール期間（開始日, 終了日, 表示ラベル）。日付は両端含む。
# お買い物マラソン/スーパーセールの日程が発表されたらここに追記する。
# 例: ("2026-08-04", "2026-08-11", "お買い物マラソン"),
SALE_PERIODS: Tuple[Tuple[str, str, str], ...] = ()

# 「5と0のつく日」（毎月5,10,15,20,25,30日）はポイントアップ日として自動判定する。
ZERO_FIVE_DAY_LINE = "きょうは5と0のつく日。楽天カード勢はポイントアップだよ"


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

# 日内枠（JST）。1日10投稿 = 商品紹介2 + 価値提供8（静的4 + ダイジェスト4）。
# 競合調査より「価値提供8:紹介2」の比率を維持する。
SLOT_LABELS: Tuple[str, ...] = (
    "07:00",  # 0: 価値（静的）
    "08:00",  # 1: 商品紹介
    "09:30",  # 2: ダイジェスト
    "12:00",  # 3: 価値（静的）
    "15:00",  # 4: ダイジェスト
    "17:00",  # 5: 価値（静的）
    "18:30",  # 6: ダイジェスト
    "20:00",  # 7: 商品紹介
    "21:00",  # 8: 価値（静的）
    "22:30",  # 9: ダイジェスト
)
POSTS_PER_DAY = len(SLOT_LABELS)

# 商品紹介（アフィリンク付き）を出す枠。朝の通勤帯と夜のゴールデンタイム。
ITEM_SLOTS: Tuple[int, ...] = (1, 7)

# ランキングダイジェスト（リンクなし・毎日内容が変わる）を出す枠。
DIGEST_SLOTS: Tuple[int, ...] = (2, 4, 6, 9)

# 静的な価値投稿（value_posts.py のプールをローテ）を出す枠。
VALUE_SLOTS: Tuple[int, ...] = (0, 3, 5, 8)

# 楽天 API エンドポイント（2025年以降の新仕様）
RAKUTEN_RANKING_URL = (
    "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
)
RAKUTEN_SEARCH_URL = (
    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601"
)
