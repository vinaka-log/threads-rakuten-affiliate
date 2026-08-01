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


# ペルソナ A の主戦場。総合は使わない。ドリンクは悩み「水が重い」側で個別指定。
GENRES: List[Genre] = [
    Genre(id="100939", label="日用品・文房具・手芸", short="日用品"),
    Genre(id="551167", label="キッチン用品・食器・調理器具", short="キッチン"),
]


@dataclass(frozen=True)
class PainIntent:
    """⑤ 悩みキーワード起点の選定単位。"""

    id: str
    # 読者の悩み（フック1行目向け・短く）
    pain: str
    # 楽天検索キーワード
    keyword: str
    # 商品名マッチ用（部分一致どれか）
    name_hints: Tuple[str, ...]
    # 優先ジャンル（空なら GENRES ローテ）
    genre_id: str
    # 使用シーン
    scene: str
    # 買う理由（一瞬で浮かぶ一文）
    buy_reason: str
    # 失敗回避
    avoid: str
    # 本投稿テンプレ固定（空なら自動）
    template_id: str = ""


# 家庭の買い足し悩み。日付×商品枠でローテ。
PAIN_INTENTS: Tuple[PainIntent, ...] = (
    PainIntent(
        id="detergent",
        pain="洗剤、また切れそうになってない？",
        keyword="洗濯洗剤 詰め替え",
        name_hints=("洗剤", "詰め替え", "液体洗剤"),
        genre_id="100939",
        scene="洗濯機まわりのストックが心もとないとき",
        buy_reason="切れてからドラッグストアに走る前に、詰め替えを宅配で足せる",
        avoid="香りが強すぎる・容量を見ずに小さい方を掴む失敗を避ける",
        template_id="hook-stock",
    ),
    PainIntent(
        id="softener",
        pain="柔軟剤、ボトル空になってから慌ててない？",
        keyword="柔軟剤 詰め替え",
        name_hints=("柔軟剤", "詰替", "詰め替え"),
        genre_id="100939",
        scene="洗濯カゴが溜まる平日の夜",
        buy_reason="詰め替えを先に置いておくと、洗濯が止まらない",
        avoid="匂い残りの合わない香りをリピしてしまう前にレビューの不満も見る",
        template_id="hook-stock",
    ),
    PainIntent(
        id="toilet-paper",
        pain="トイレットペーパー、残り何個か把握してる？",
        keyword="トイレットペーパー まとめ買い",
        name_hints=("トイレットペーパー", "トイレ", "シングル", "ダブル"),
        genre_id="100939",
        scene="夜中に芯だけ発見したくないとき",
        buy_reason="まとめ買いなら重いし、届けてもらった方が楽",
        avoid="シングル/ダブルと芯ありなしの取り違えに注意",
        template_id="hook-heavy",
    ),
    PainIntent(
        id="tissue",
        pain="ティッシュ、箱ごとに買い足してない？",
        keyword="ティッシュ ボックス まとめ",
        name_hints=("ティッシュ", "ボックスティッシュ", "ソフトパック"),
        genre_id="100939",
        scene="リビングと寝室で同時に空になるパターン",
        buy_reason="ケース買いだと単価が落ちて、補充の手間も減る",
        avoid="ソフトパックと箱の置き場所を確認してから選ぶ",
        template_id="hook-stock",
    ),
    PainIntent(
        id="trash-bag",
        pain="ゴミ袋、レジ袋で凌いでない？",
        keyword="ゴミ袋 半透明",
        name_hints=("ゴミ袋", "ポリ袋", "ごみ袋"),
        genre_id="100939",
        scene="ゴミの日の朝に袋がないとき",
        buy_reason="指定サイズをまとめ買いしておくと朝の慌てがなくなる",
        avoid="自治体の色・厚さ指定を見落とさない",
        template_id="hook-tonight",
    ),
    PainIntent(
        id="water-case",
        pain="水、まだ店で抱えて帰ってる？",
        keyword="水 ケース ラベルレス",
        name_hints=("水", "ラベルレス", "天然水", "2L", "ケース"),
        genre_id="100227",
        scene="買い出し帰りが重くてしんどい日",
        buy_reason="ケース水は宅配が本領。ポイント日に寄せるとなお良い",
        avoid="置き場所（箱の高さ）を測ってから決める",
        template_id="hook-heavy",
    ),
    PainIntent(
        id="wrap",
        pain="ラップ、引き出しの奥で切れかけてない？",
        keyword="サランラップ 詰め替え",
        name_hints=("ラップ", "サランラップ", "保鲜膜"),
        genre_id="551167",
        scene="お弁当や作り置きの朝",
        buy_reason="替え玉を先に置いておくと、朝の小パニックが消える",
        avoid="幅（22cm/30cm）の取り違えに注意",
        template_id="hook-stock",
    ),
    PainIntent(
        id="dish-sponge",
        pain="スポンジ、ヌメってきたら替え時だよ",
        keyword="キッチン スポンジ 抗菌",
        name_hints=("スポンジ", "キッチンスポンジ", "食器洗い"),
        genre_id="551167",
        scene="洗い物のたびに気になる衛生感",
        buy_reason="安くて消耗品だから、まとめ買いが一番コスパいい",
        avoid="油汚れ用とグラス用を分けた方が持ちがいい",
        template_id="hook-reason",
    ),
    PainIntent(
        id="dishwasher-tab",
        pain="食洗機の洗剤、残り少なくない？",
        keyword="食洗機 洗剤 タブレット",
        name_hints=("食洗機", "タブレット", "ジェル", "フィニッシュ", "キュキュット"),
        genre_id="551167",
        scene="食洗機を回すたびに減っていくストック",
        buy_reason="大容量にすると買い忘れと単価の両方を減らせる",
        avoid="機種の専用指定（粉/タブ/ジェル）を確認",
        template_id="hook-stock",
    ),
    PainIntent(
        id="kitchen-paper",
        pain="キッチンペーパー、料理中に切れたことない？",
        keyword="キッチンペーパー 詰め替え",
        name_hints=("キッチンペーパー", "クッキングペーパー"),
        genre_id="551167",
        scene="揚げ物や肉の下処理の最中",
        buy_reason="替えを棚に1個あるだけで調理が止まらない",
        avoid="ホルダーサイズに合うかだけ先に見る",
        template_id="hook-tonight",
    ),
)

# 商品投稿に楽天の商品画像を付ける（⑥）
ATTACH_ITEM_IMAGE = True

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
