"""Threads × 楽天アフィリエイト 自動投稿の設定。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

# リポジトリルート
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
LEDGER_PATH = DATA_DIR / "posted.json"

# ---------------------------------------------------------------------------
# ペルソナ B（固定）
#   誰に: 妊娠中〜未就学（特に0〜2歳）の買い足し担当
#   何を: ベビーグッズの「これから買う／買い直す」候補メモ
#   何の人か: 売れ筋と口コミから、買う理由だけ先に教えるしろくま
#   表示名: かいものくま｜0〜2歳の買い足しメモ
#   やらない: 日用品総合・美容・ファッション・ガジェット・なんでも売れ筋
# ---------------------------------------------------------------------------
PERSONA_ID = "baby-gear"
PERSONA_LABEL = "0〜2歳のベビーグッズ買い"
PERSONA_AUDIENCE = "妊娠中〜未就学（特に0〜2歳）の買い足し担当"
PERSONA_PROMISE = "これから買うベビーグッズの買い足しメモ"
PERSONA_DISPLAY_NAME = "かいものくま｜0〜2歳の買い足しメモ"
PERSONA_BIO = (
    "╲0〜2歳の買い足しを楽天に寄せたい人へ╱\n"
    "ベビーグッズの買い時を毎日メモ\n"
    "・お出かけ・ねんね・収納の候補\n"
    "・売れ筋と口コミの定点観測\n"
    "・ポイント日・セールの目安\n"
    "PR・アフィリエイトリンクを含みます"
)
# Threads 投稿の文字数上限（余裕を持って短めに）
MAX_TEXT_LEN = 480

# 同一 itemCode の再投稿禁止日数
DEDUP_DAYS = 30

# 紹介品質フィルタ
MIN_REVIEW_AVERAGE = 4.3
MIN_REVIEW_COUNT = 80
# ベビーグッズは枕・収納などで消耗品より高い。超高額家電は除外
MAX_ITEM_PRICE = 10000
# 送料別は敬遠されやすいので、送料込を優先（取れなければ送料別も可）
PREFER_POSTAGE_INCLUDED = True
# True にすると送料込以外を候補から除外（品薄時は投稿失敗しうる）
REQUIRE_POSTAGE_INCLUDED = False

# 商品名に含まれていたら除外（ペルソナ外）
BLOCK_NAME_HINTS: Tuple[str, ...] = (
    "美容液",
    "セラム",
    "化粧水",
    "乳液",
    "日焼け止め",
    "ファンデーション",
    "シャンプー",
    "トリートメント",
    "化粧品",
    "サプリ",
    "プロテイン",
    "炊飯器",
    "掃除機",
    "エアコン",
    "テレビ",
    "スマホ",
    "iphone",
    "ipad",
    "ノートパソコン",
    "デスクトップ",
    # 大人向け・ペルソナ外
    "ワイン",
    "ウイスキー",
    "サッポロクラシック",
    "液体洗剤",
    "柔軟剤つめかえ",
)

# ランキング取得件数（上位からフィルタ）
RANKING_HITS = 30

# rank帯ローテ: 日替わりで「上位帯」と「準上位帯」を交互に紹介する。
RANK_BANDS: Tuple[Tuple[int, int], ...] = (
    (1, 10),
    (11, 30),
)

# セール期間（開始日, 終了日, 表示ラベル）。日付は両端含む。
SALE_PERIODS: Tuple[Tuple[str, str, str], ...] = (
    ("2026-09-04", "2026-09-11", "楽天スーパーSALE"),
)

# 「5と0のつく日」（毎月5,10,15,20,25,30日）はポイントアップ日として自動判定する。
ZERO_FIVE_DAY_LINE = "きょうは5と0のつく日（楽天カード勢はポイントアップ）"


@dataclass(frozen=True)
class Genre:
    id: str
    label: str
    # 投稿文で使う短いカテゴリ名
    short: str


# ペルソナ B の主戦場。総合・日用品総合は使わない。
GENRES: List[Genre] = [
    Genre(id="100533", label="キッズ・ベビー・マタニティ", short="ベビー"),
    Genre(id="200833", label="ベビーカー", short="お出かけ"),
    Genre(id="200822", label="ベビー用寝具・ベッド", short="ねんね"),
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
    # 困っている場面
    scene: str
    # 買わないと続く困り（Before）
    problem: str
    # 買うとどう楽になるか（After / ベネフィット）
    benefit: str
    # 買う理由（補足）
    buy_reason: str
    # 失敗回避
    avoid: str
    # 本投稿テンプレ固定（空なら自動）
    template_id: str = ""
    # 追加でどれか必須
    require_name_hints: Tuple[str, ...] = ()
    # 含まれていたら除外
    exclude_name_hints: Tuple[str, ...] = ()
    # 容量表記を必須にするか（消耗品向け。ベビーグッズは基本 False）
    require_size_token: bool = False
    # 時短アイテム枠（TIMESAVE_ITEM_SLOTS）のローテ対象か
    timesave: bool = False
    # 悩みごとの価格上限（空なら MAX_ITEM_PRICE）
    max_price: Optional[int] = None


# 0〜2歳の買い足し悩み。日付×商品枠でローテ。
# problem / benefit / avoid / scene は短め口語（テスト上限あり）。
PAIN_INTENTS: Tuple[PainIntent, ...] = (
    PainIntent(
        id="stroller-rain",
        pain="急な雨、ベビーカーどうしてる？",
        keyword="ベビーカー レインカバー",
        name_hints=("レインカバー", "レインコート ベビーカー", "ベビーカーカバー"),
        genre_id="200833",
        scene="公園帰りに空が怪しいとき",
        problem="雨に打たれて荷物も子もびしょびしょ",
        benefit="カバーあればお出かけが止まらない",
        buy_reason="天気は読めない、備えが本体",
        avoid="対応機種と窓の位置だけ確認",
        exclude_name_hints=("大人用", "自転車", "バイク"),
    ),
    PainIntent(
        id="stroller-gear",
        pain="ベビーカー周り、何か足りてない？",
        keyword="ベビーカー アクセサリー",
        name_hints=("ベビーカー", "バギー", "ベビーカーバッグ", "ドリンクホルダー"),
        genre_id="200833",
        scene="お出かけ準備で手が足りない朝",
        problem="小物散らばると出発が毎回遅れる",
        benefit="置き場決まると支度が短くなる",
        buy_reason="お出かけは周辺グッズで楽になる",
        avoid="取り付け方と干渉、レビュー見て",
        exclude_name_hints=("レインカバー", "チャイルドシート", "自転車"),
        timesave=True,
    ),
    PainIntent(
        id="baby-towel",
        pain="沐浴タオル、まだ薄手で凌いでない？",
        keyword="ベビー バスタオル イブル",
        name_hints=("バスタオル", "イブル", "ガーゼタオル", "沐浴タオル"),
        genre_id="100533",
        scene="上がりの冷えが気になる夜",
        problem="薄手だと乾き待ちでバタバタする",
        benefit="一枚あると上がりが落ち着く",
        buy_reason="毎日使うものほど先に揃える",
        avoid="厚みと洗濯表記、先にチェック",
        require_name_hints=("ベビー", "赤ちゃん", "イブル", "ガーゼ", "沐浴"),
    ),
    PainIntent(
        id="baby-pillow",
        pain="ねんね姿勢、気になってない？",
        keyword="ベビー枕 ジオピロー",
        name_hints=("ベビー枕", "ベビーまくら", "新生児 枕", "ジオピロー"),
        genre_id="200822",
        scene="夜の寝かしつけが長いとき",
        problem="姿勢不安のまま夜が長引く",
        benefit="合う枕だと見守りが少し楽",
        buy_reason="ねんねは毎晩続くから先行投資",
        avoid="月齢と向き癖、説明見て判断",
        max_price=12000,
    ),
    PainIntent(
        id="diaper-stock",
        pain="おむつ山、床に散らばってない？",
        keyword="おむつストッカー",
        name_hints=("おむつストッカー", "オムツストッカー", "おむつ収納"),
        genre_id="100533",
        scene="夜中の替えで床を探るとき",
        problem="暗がり探しで起こしがちになる",
        benefit="定位置あると夜間が短くなる",
        buy_reason="収納は睡眠時間の確保装置",
        avoid="置き場サイズと取り出しやすさ",
        timesave=True,
    ),
    PainIntent(
        id="kids-hanger",
        pain="子ども服、床置き増えてない？",
        keyword="キッズ ハンガーラック",
        name_hints=("ハンガーラック", "キッズハンガー", "子供服 ハンガー"),
        genre_id="100533",
        scene="朝の着替えで床が戦場のとき",
        problem="探せないまま遅刻しそうになる",
        benefit="手が届く高さだと自分で取れる",
        buy_reason="片付け習慣は道具で作る",
        avoid="転倒防止と高さ調節を確認",
        require_name_hints=("キッズ", "子供", "子ども", "ジュニア", "ベビー"),
    ),
    PainIntent(
        id="handprint",
        pain="手形足形、まだ撮れてない？",
        keyword="手形 スタンプ パームカラーズ",
        name_hints=("手形", "足形", "パームカラーズ", "スタンプパッド"),
        genre_id="100533",
        scene="急に小さく感じる夜",
        problem="先延ばしするとサイズが変わる",
        benefit="インク式なら汚れを抑えやすい",
        buy_reason="記録は今しか取れない買い物",
        avoid="対象月齢と色移り注意を確認",
    ),
    PainIntent(
        id="baby-wipes",
        pain="おしりふき、カバンの中空じゃない？",
        keyword="おしりふき 詰め替え",
        name_hints=("おしりふき", "お尻拭き", "ベビーシート"),
        genre_id="100533",
        scene="外出先で替えたい瞬間",
        problem="切れに気づくと外出が詰まる",
        benefit="替えあればお出かけが止まらない",
        buy_reason="消耗品は切れない仕組みが大事",
        avoid="携帯用と詰め替え、用途分けて",
        require_name_hints=("おしり", "お尻", "ベビー"),
        exclude_name_hints=("大人用", "体ふき", "車用"),
    ),
    PainIntent(
        id="diapers",
        pain="おむつサイズ、まだギリギリで粘してない？",
        keyword="おむつ パンツ 新生児",
        name_hints=("おむつ", "オムツ", "パンツタイプ", "テープタイプ"),
        genre_id="100533",
        scene="モレが気になり始めた週",
        problem="サイズ遅れは洗濯も気分も増える",
        benefit="合ってると夜間のモレ不安が減る",
        buy_reason="合わないおむつがいちばん高い",
        avoid="体重目安とパンツ/テープ確認",
        require_name_hints=("おむつ", "オムツ", "パンツ", "テープ"),
        exclude_name_hints=("ストッカー", "ポーチ", "ケース", "消臭"),
    ),
    PainIntent(
        id="baby-carrier",
        pain="抱っこ移動、腕が限界になってない？",
        keyword="抱っこひも 新生児",
        name_hints=("抱っこひも", "抱っこ紐", "ベビースリング", "ヒップシート"),
        genre_id="100533",
        scene="両手ほしい買い物や駅の移動",
        problem="腕抱っこだと荷物が持てない",
        benefit="両手空くと移動が一気に楽",
        buy_reason="移動のしんどさは毎日積み上がる",
        avoid="月齢対応と装着レビューを見て",
        timesave=True,
        max_price=15000,
    ),
)

# 時短枠専用は当面空（timesave フラグの悩みを通常ローテ側で扱う）。
TIMESAVE_ONLY_INTENTS: Tuple[PainIntent, ...] = ()


def all_pain_intents() -> Tuple[PainIntent, ...]:
    """通常悩み + 時短専用悩み。"""
    return tuple(PAIN_INTENTS) + tuple(TIMESAVE_ONLY_INTENTS)


def timesave_pain_intents() -> Tuple[PainIntent, ...]:
    """時短枠ローテ用（時短専用を先に、続けて timesave フラグ）。"""
    marked = tuple(p for p in PAIN_INTENTS if p.timesave)
    return tuple(TIMESAVE_ONLY_INTENTS) + marked

# 本投稿に楽天商品画像を付けない（カタログ／アフィ感が出る）。メモリプで商品名だけ出す。
ATTACH_ITEM_IMAGE = False

# 日内枠（JST）。1日10投稿 = アンケート3 + 雑談3 + ジブリ大喜利2 + 商品紹介2。
# repo は public のため Actions 枠は消費しない。ずらし複数 cron は使わない。
SLOT_LABELS: Tuple[str, ...] = (
    "08:00",  # 0: アンケート
    "09:30",  # 1: 雑談
    "11:00",  # 2: ジブリ大喜利
    "12:30",  # 3: アンケート
    "14:00",  # 4: 雑談
    "16:00",  # 5: 商品紹介
    "18:00",  # 6: ジブリ大喜利
    "19:30",  # 7: アンケート
    "21:00",  # 8: 雑談
    "22:00",  # 9: 商品紹介
)
POSTS_PER_DAY = len(SLOT_LABELS)

# 商品紹介は1日2本（16:00 / 22:00）。
ITEM_SLOTS: Tuple[int, ...] = (5, 9)
# 時短専用枠は当面停止（timesave 悩みは通常ローテ側で扱う）。
TIMESAVE_ITEM_SLOTS: Tuple[int, ...] = ()

# ランキングダイジェストは一旦停止。
DIGEST_SLOTS: Tuple[int, ...] = ()

# ジブリ大喜利（画像＋短文・PRなし）。0〜2歳の買い足しあるある。
OGIRI_SLOTS: Tuple[int, ...] = (2, 6)

# 価値投稿枠（リンクなし）= アンケート + 雑談。大喜利は OGIRI_SLOTS。
VALUE_SLOTS: Tuple[int, ...] = (0, 1, 3, 4, 7, 8)

# 共働きリアル苦悩は当面停止（アンケート優先）。
STRUGGLE_SLOTS: Tuple[int, ...] = ()

# テーマ無関係の雑談（一度きり・自動補充）。
CHITCHAT_SLOTS: Tuple[int, ...] = (1, 4, 8)
CHITCHAT_POOL_PATH = DATA_DIR / "chitchat_pool.json"
CHITCHAT_MIN_UNUSED = 6
CHITCHAT_REFILL_COUNT = 10

# アンケート（問いかけ）枠。アイス投稿と同型。季節 + 軽いトレンド。商品・PRなし。
ASK_CHITCHAT_SLOTS: Tuple[int, ...] = (0, 3, 7)
ASK_CHITCHAT_POOL_PATH = DATA_DIR / "ask_chitchat_pool.json"
TREND_SEEDS_PATH = DATA_DIR / "trend_seeds.json"
ASK_CHITCHAT_MIN_UNUSED = 6
ASK_CHITCHAT_REFILL_COUNT = 10

# 伸びた価値投稿の再利用。アンケートは一度きりなので枠は空。
REUSE_INTERVAL_DAYS = 3
REUSE_SLOTS: Tuple[int, ...] = ()
REUSE_PATH = DATA_DIR / "reuse.json"
REUSE_WINNER_MIN_VIEWS = 500

# 楽天 API エンドポイント（2025年以降の新仕様）
RAKUTEN_RANKING_URL = (
    "https://openapi.rakuten.co.jp/ichibaranking/api/IchibaItem/Ranking/20220601"
)
RAKUTEN_SEARCH_URL = (
    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601"
)
