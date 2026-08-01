"""Threads × 楽天アフィリエイト 自動投稿の設定。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# リポジトリルート
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
LEDGER_PATH = DATA_DIR / "posted.json"

# ---------------------------------------------------------------------------
# ペルソナ A（固定）
#   誰に: 共働き〜小さな子どもがいる家庭で、日々の買い物を楽天に寄せている人
#   何を: 消耗品・キッチンまわりの「また切れた」を減らす買い時メモ
#   何の人か: 毎日ランキングを見て、買う理由だけ先に教えるしろくま
#   表示名: かいものくま｜日用品の買い時メモ
#   やらない: 美容・ファッション・ガジェット総合・なんでも売れ筋
# ---------------------------------------------------------------------------
PERSONA_ID = "household-stock"
PERSONA_LABEL = "家庭の消耗品・時短買い"
PERSONA_AUDIENCE = "共働き〜子育て世帯の日々の買い足し担当"
PERSONA_PROMISE = "また切れた…を減らす日用品の買い時メモ"
PERSONA_DISPLAY_NAME = "かいものくま｜日用品の買い時メモ"
PERSONA_BIO = (
    "╲また切れた…を減らしたい共働きへ╱\n"
    "日用品とキッチンの買い時を毎日メモ\n"
    "・売れ筋ランキングの定点観測\n"
    "・重いもの・ストック補充の候補\n"
    "・ポイント日・セールの目安\n"
    "PR・アフィリエイトリンクを含みます"
)
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


# ペルソナ A の主戦場のみ。総合ランキングは美容・ガジェットが混ざるので使わない。
GENRES: List[Genre] = [
    Genre(id="100939", label="日用品・文房具・手芸", short="日用品"),
    Genre(id="551167", label="キッチン用品・食器・調理器具", short="キッチン"),
    Genre(id="100227", label="水・ソフトドリンク", short="ドリンク"),
]

# 日内枠（JST）。1日10投稿 = 商品紹介2 + 価値提供8（静的4 + ダイジェスト4）。
# 夕方〜夜（17/18/19/20時台）を厚くし、家庭の買い足しタイムに合わせる。
SLOT_LABELS: Tuple[str, ...] = (
    "07:00",  # 0: 価値（静的）朝の支度前
    "08:00",  # 1: 商品紹介
    "12:00",  # 2: 価値（静的）昼休み
    "15:00",  # 3: ダイジェスト
    "17:00",  # 4: 価値（静的）帰宅・夕飯準備帯
    "18:00",  # 5: ダイジェスト
    "19:00",  # 6: ダイジェスト
    "20:00",  # 7: 商品紹介（ゴールデン）
    "21:00",  # 8: 価値（静的）
    "22:00",  # 9: ダイジェスト
)
POSTS_PER_DAY = len(SLOT_LABELS)

# 商品紹介（アフィリンク付き）を出す枠。朝の買い足し帯と夜のゴールデンタイム。
ITEM_SLOTS: Tuple[int, ...] = (1, 7)

# ランキングダイジェスト（リンクなし・毎日内容が変わる）を出す枠。
DIGEST_SLOTS: Tuple[int, ...] = (3, 5, 6, 9)

# 静的な価値投稿（value_posts.py のプールをローテ）を出す枠。
VALUE_SLOTS: Tuple[int, ...] = (0, 2, 4, 8)

# 伸びた価値投稿の再利用（参考: 3日に1回）。
# REUSE_SLOTS では通常ローテより再利用キューを優先する。
REUSE_INTERVAL_DAYS = 3
REUSE_SLOTS: Tuple[int, ...] = (4,)  # 17:00 帰宅帯
REUSE_PATH = DATA_DIR / "reuse.json"
# Insights 連携時、この views 以上を「伸びた」とみなして優先度を上げる
REUSE_WINNER_MIN_VIEWS = 500

# 楽天 API エンドポイント（2025年以降の新仕様）
RAKUTEN_RANKING_URL = (
    "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
)
RAKUTEN_SEARCH_URL = (
    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601"
)
