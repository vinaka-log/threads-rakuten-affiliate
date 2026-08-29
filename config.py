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
MIN_REVIEW_COUNT = 100
# 消耗品の時短買い向け。高額美容・家電を混ぜない
MAX_ITEM_PRICE = 3000
# 送料別は敬遠されやすいので、送料込を優先（取れなければ送料別も可）
PREFER_POSTAGE_INCLUDED = True
# True にすると送料込以外を候補から除外（品薄時は投稿失敗しうる）
REQUIRE_POSTAGE_INCLUDED = False

# 商品名に含まれていたら除外（ペルソナ外）
# 注意: 「香水」「コスメ」「クリーム」は「香水調」「アットコスメ」等に誤爆するため使わない
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
    # 消耗品本体ではなく周辺グッズ（洗剤コピーにボトル/収納が載る事故防止）
    "詰め替えボトル",
    "洗剤ボトル",
    "ディスペンサー",
    "詰め替え容器",
    "空容器",
    "ポンプボトル",
    "ボトル単品",
    "ストッカー",
    "洗剤入れ",
    "ボールストッカー",
    "洗面所収納",
    "ランドリー収納",
    # 消耗品の周辺ガジェット（悩みコピーにホルダー等が載る事故防止）
    "ラップホルダー",
    "ラップケース",
    "ワイパースタンド",
    "フローリングワイパースタンド",
)

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
ZERO_FIVE_DAY_LINE = "きょうは5と0のつく日（楽天カード勢はポイントアップ）"


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
    # 追加でどれか必須（つめかえ/容量など消耗品らしい語）
    require_name_hints: Tuple[str, ...] = ()
    # 含まれていたら除外（収納グッズ等）
    exclude_name_hints: Tuple[str, ...] = ()
    # 容量表記（2900g / 1285mL 等）を必須にするか
    require_size_token: bool = False
    # 時短アイテム枠（TIMESAVE_ITEM_SLOTS）のローテ対象か
    timesave: bool = False
    # 悩みごとの価格上限（空なら MAX_ITEM_PRICE）。ケース買いなど向け。
    max_price: Optional[int] = None


_CONSUMABLE_STORAGE_EXCLUDES: Tuple[str, ...] = (
    "ストッカー",
    "収納",
    "ホルダー",
    "スタンド",
    "ラック",
    "ディスペンサー",
    "ボトル",
    "容器",
    "洗剤入れ",
    "マグネット",
    "山崎実業",
)


# 家庭の買い足し悩み。日付×商品枠でローテ。
# problem / benefit / avoid は短め口語（本投稿〜140字・リプ事実欄向け）。
# name_hints は誤マッチしやすい汎用語（詰め替え等）を避け、商品固有語のみにする。
PAIN_INTENTS: Tuple[PainIntent, ...] = (
    PainIntent(
        id="detergent",
        pain="洗剤、また切れそうになってない？",
        keyword="液体洗剤 つめかえ",
        name_hints=("液体洗剤", "衣料用洗剤", "粉洗剤", "洗たく洗剤", "ジェルボール", "ゲルボール"),
        genre_id="100939",
        scene="ボトルが軽い夜",
        problem="切れた瞬間に洗濯止まって、残業後のドラ行きになる",
        benefit="詰め替え先置きで、洗濯が止まらない",
        buy_reason="切れてから買うのがいちばん高い",
        avoid="香り強めもあるし、容量見ないと損しやすい",
        template_id="",
        require_name_hints=("つめかえ", "詰め替え", "詰替", "ジェルボール", "ゲルボール"),
        exclude_name_hints=_CONSUMABLE_STORAGE_EXCLUDES
        + (
            "漂白剤",
            "漂白",
            "ハイター",
            "衣料用漂白剤",
            "洗たく槽",
        ),
        require_size_token=True,
    ),
    PainIntent(
        id="softener",
        pain="柔軟剤、ボトル空になってから慌ててない？",
        keyword="柔軟剤 つめかえ",
        name_hints=("柔軟剤",),
        genre_id="100939",
        scene="カゴ溜まってるのにボトル空の平日",
        problem="空だと洗濯止まって、着替えが詰まる",
        benefit="替えがあれば朝のパニック減る",
        buy_reason="柔軟剤切れは家事全体の詰まり",
        avoid="香りの好みはレビュー見てからの方が安心",
        template_id="",
        require_name_hints=("つめかえ", "詰め替え", "詰替"),
        exclude_name_hints=_CONSUMABLE_STORAGE_EXCLUDES,
        require_size_token=True,
    ),
    PainIntent(
        id="toilet-paper",
        pain="トイレットペーパー、残り何個か把握してる？",
        keyword="トイレットペーパー ダブル",
        # 「トイレットティシュー」は主要ブランドの表記ゆれ
        name_hints=("トイレットペーパー", "トイレットティシュー", "トイレロール"),
        genre_id="100939",
        scene="夜中に芯だけ発見したくないとき",
        problem="最悪のタイミングで深夜に走ることになる",
        benefit="まとめ買い宅配なら切れリスク先に潰せる",
        buy_reason="重い消耗品は届けてもらう方が楽",
        avoid="シングル/ダブルと芯ありなし、取り違え注意",
        template_id="",
        require_name_hints=("ロール", "シングル", "ダブル", "芯なし", "芯あり"),
        # 「ケース買い」など消耗品表記に誤爆しないよう、収納グッズ固有語だけ除外
        exclude_name_hints=(
            "ティッシュケース",
            "ペーパーポット",
            "ペーパーホルダー",
            "トイレットペーパーホルダー",
            "ロールホルダー",
            "カバー",
            "スタンド",
            "ディスペンサー",
        ),
        require_size_token=True,
    ),
    PainIntent(
        id="tissue",
        pain="ティッシュ、箱ごとに買い足してない？",
        keyword="ティッシュペーパー ボックス",
        name_hints=("ティッシュペーパー", "ボックスティッシュ", "ティシュー"),
        genre_id="100939",
        scene="リビングと寝室が同時に空になる日",
        problem="箱ごとに買うと単価も手間も増える",
        benefit="ケース買いなら補充回数が減る",
        buy_reason="毎日使うものほど、まとめが効く",
        avoid="箱かソフトパックか、置き場だけ先に確認",
        template_id="",
        require_name_hints=("組", "箱", "個", "パック", "ソフトパック"),
        exclude_name_hints=(
            "ティッシュケース",
            "ティッシュカバー",
            "ペーパーホルダー",
            "ホルダー",
            "スタンド",
            "ディスペンサー",
        ),
        require_size_token=True,
    ),
    PainIntent(
        id="trash-bag",
        pain="ゴミ袋、レジ袋で凌いでない？",
        keyword="ゴミ袋 半透明",
        name_hints=("ゴミ袋", "ごみ袋"),
        genre_id="100939",
        scene="ゴミの日の朝に指定袋がないとき",
        problem="朝の出発が遅れて、最悪一週間持ち越す",
        benefit="指定サイズ先積みで、朝の慌てが消える",
        buy_reason="ゴミ袋切れは時間も気力も持っていく",
        avoid="自治体の色・厚さ指定は要チェック",
        template_id="",
    ),
    PainIntent(
        id="water-case",
        pain="水、まだ店で抱えて帰ってる？",
        keyword="天然水 ラベルレス",
        name_hints=("天然水", "ラベルレス", "ミネラルウォーター"),
        genre_id="100227",
        scene="買い出し帰りが重くてしんどい日",
        problem="重い水を運ぶたびに、他の家事まで崩れる",
        benefit="ケース水宅配なら、腕も時間も空く",
        buy_reason="水は運ばなくていい仕組みが本体",
        avoid="箱の高さ、置き場測ってからが無難",
        template_id="",
        timesave=True,
    ),
    PainIntent(
        id="beer-sapporo-classic",
        pain="ビール、また店でケース抱えてない？",
        keyword="サッポロクラシック 350ml 24本",
        name_hints=("サッポロクラシック", "サッポロ クラシック"),
        genre_id="100316",
        scene="週末前にケースが空の夜",
        problem="重い缶を運ぶと他の買い物も崩れる",
        benefit="宅配なら運ぶ手間が消える",
        buy_reason="重い飲みものは届けてもらう前提",
        avoid="季節限定と取り違え注意",
        template_id="",
        require_name_hints=("クラシック",),
        exclude_name_hints=(
            "夏の爽快",
            "黒ラベル",
            "赤星",
            "エビス",
            "ヱビス",
            "プレミアムアルコールフリー",
            "ノンアル",
            "ジョッキ",
            "グラス",
            "サーバー",
        ),
        timesave=True,
        max_price=6000,
    ),
    PainIntent(
        id="wrap",
        pain="ラップ、引き出しの奥で切れかけてない？",
        keyword="サランラップ",
        name_hints=("サランラップ", "食品用ラップ", "ラップフィルム"),
        genre_id="551167",
        scene="お弁当や作り置きの朝",
        problem="朝いちで切れると、支度が全部遅れる",
        benefit="替え玉があれば朝の小パニック消える",
        buy_reason="朝に効く消耗品は、前夜の自分への投資",
        avoid="22cm/30cmの取り違え注意",
        template_id="",
        # SEOで「サランラップ」が付いたホルダー/ケースを除外
        exclude_name_hints=_CONSUMABLE_STORAGE_EXCLUDES
        + (
            "ホルダー",
            "ケース",
            "ideaco",
            "イデアコ",
            "マグネット",
            "収納",
            "ラップカッター",
        ),
        timesave=True,
    ),
    PainIntent(
        id="dish-sponge",
        pain="スポンジ、ヌメってきたら替え時だよ",
        keyword="キッチンスポンジ 抗菌",
        name_hints=("キッチンスポンジ", "食器洗いスポンジ", "スポンジたわし"),
        genre_id="551167",
        scene="洗い物のたび衛生感が気になるとき",
        problem="替え時逃すと、気持ち悪さが毎日続く",
        benefit="まとめ買いなら迷わず交換できる",
        buy_reason="安い消耗品ほど、決断コストをゼロに",
        avoid="油用とグラス用、分けた方が持ちいい",
        template_id="",
    ),
    PainIntent(
        id="dishwasher-tab",
        pain="食洗機の洗剤、残り少なくない？",
        keyword="食洗機 洗剤 タブレット",
        name_hints=("食洗機用", "食器洗い機用", "食洗機洗剤", "食洗機用洗剤"),
        genre_id="551167",
        scene="回すたびに減っていくストック",
        problem="切れると手洗い戻りで、夜が一気に重い",
        benefit="大容量先置きで、時短家電が止まらない",
        buy_reason="食洗機は洗剤があって初めて時短装置",
        avoid="粉/タブ/ジェルの機種指定だけ確認",
        template_id="",
        timesave=True,
    ),
    PainIntent(
        id="kitchen-paper",
        pain="キッチンペーパー、料理中に切れたことない？",
        keyword="キッチンペーパー",
        name_hints=("キッチンペーパー", "クッキングペーパー"),
        genre_id="551167",
        scene="揚げ物や肉の下処理の最中",
        problem="調理中に切れると、手が止まって片付け雑になる",
        benefit="替え1個あるだけで調理が止まらない",
        buy_reason="料理中の切れがいちばん腹立たしい",
        avoid="ホルダーサイズ合うかだけ見て",
        template_id="",
    ),
)

# 時短枠専用（通常の商品ローテ長をずらさない）。ガジェット本体ではなく替え消耗品。
TIMESAVE_ONLY_INTENTS: Tuple[PainIntent, ...] = (
    PainIntent(
        id="floor-wiper",
        pain="床掃除、水拭きまで手が回ってる？",
        keyword="クイックルワイパー シート",
        name_hints=(
            "フローリングワイパー",
            "フロアワイパー",
            "クイックルワイパー",
            "クイックル",
            "取り替えシート",
            "ドライシート",
            "ウェットシート",
            "ウエットシート",
        ),
        genre_id="100939",
        scene="帰宅直後に床の砂や髪が気になる夜",
        problem="溜めると休日が掃除デーになって消える",
        benefit="替えシートあれば、夜の片付け5分で終わる",
        buy_reason="時短は道具本体より、替えが切れないこと",
        avoid="ドライ/ウェットと本体サイズ要確認",
        template_id="",
        require_name_hints=("シート",),
        exclude_name_hints=(
            "本体セット",
            "ハンドル付き",
            "伸縮ポール",
            "スタンド",
            "ホルダー",
            "収納",
            "山崎実業",
        ),
        require_size_token=False,
        timesave=True,
    ),
)


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

# ジブリ大喜利（画像＋短文・PRなし）。家庭の買い足しあるある。
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
