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
MIN_REVIEW_AVERAGE = 4.3
MIN_REVIEW_COUNT = 100
# 消耗品の時短買い向け。高額美容・家電を混ぜない
MAX_ITEM_PRICE = 3000

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
# problem / benefit で「買うとその人にどう役立つか」を必ず言えるようにする。
# name_hints は誤マッチしやすい汎用語（詰め替え等）を避け、商品固有語のみにする。
PAIN_INTENTS: Tuple[PainIntent, ...] = (
    PainIntent(
        id="detergent",
        pain="洗剤、また切れそうになってない？",
        keyword="洗濯洗剤 つめかえ",
        name_hints=("洗濯洗剤", "衣料用洗剤", "液体洗剤", "粉洗剤", "洗たく洗剤"),
        genre_id="100939",
        scene="洗濯しようとしたらボトルが軽い夜",
        problem="切れた瞬間に洗濯が止まり、残業後のドラッグストア行きが発生する",
        benefit="詰め替えを先に置いておけば、洗濯が止まらず寄り道も減る",
        buy_reason="共働きの平日は「切れてから買う」が一番高いコスト",
        avoid="香りが強すぎる・容量を見ずに小さい方を掴む失敗を避ける",
        template_id="hook-benefit",
        require_name_hints=("つめかえ", "詰め替え", "詰替", "ジェルボール", "ゲルボール"),
        exclude_name_hints=_CONSUMABLE_STORAGE_EXCLUDES,
        require_size_token=True,
    ),
    PainIntent(
        id="softener",
        pain="柔軟剤、ボトル空になってから慌ててない？",
        keyword="柔軟剤 つめかえ",
        name_hints=("柔軟剤",),
        genre_id="100939",
        scene="洗濯カゴが溜まってるのにボトルが空の平日",
        problem="空だと洗濯コースが止まり、衣類が部屋に滞留する",
        benefit="替えがあるだけで洗濯が回り続け、朝の着替えパニックが減る",
        buy_reason="柔軟剤切れは家事全体の詰まりに直結する",
        avoid="匂い残りの合わない香りをリピする前にレビューの不満も見る",
        template_id="hook-benefit",
        require_name_hints=("つめかえ", "詰め替え", "詰替"),
        exclude_name_hints=_CONSUMABLE_STORAGE_EXCLUDES,
        require_size_token=True,
    ),
    PainIntent(
        id="toilet-paper",
        pain="トイレットペーパー、残り何個か把握してる？",
        keyword="トイレットペーパー",
        name_hints=("トイレットペーパー", "トイレロール"),
        genre_id="100939",
        scene="夜中に芯だけを発見したくないとき",
        problem="切れに気づくのが最悪のタイミングで、誰かが深夜に走る羽目になる",
        benefit="まとめ買い宅配なら重労働なしで、切れリスクを先に潰せる",
        buy_reason="重い消耗品ほど、店で抱えるより届けてもらう方が生活が楽",
        avoid="シングル/ダブルと芯ありなしの取り違えに注意",
        template_id="hook-benefit",
    ),
    PainIntent(
        id="tissue",
        pain="ティッシュ、箱ごとに買い足してない？",
        keyword="ティッシュペーパー",
        name_hints=("ティッシュペーパー", "ボックスティッシュ", "ティシュー"),
        genre_id="100939",
        scene="リビングと寝室で同時に空になるパターン",
        problem="箱ごとに買うと単価も手間も増え、気づくたびに小さなストレスが積もる",
        benefit="ケース買いなら補充回数が減り、単価も下がって家計と手間の両方助かる",
        buy_reason="毎日使うものほど、まとめが効く",
        avoid="ソフトパックと箱の置き場所を確認してから選ぶ",
        template_id="hook-benefit",
    ),
    PainIntent(
        id="trash-bag",
        pain="ゴミ袋、レジ袋で凌いでない？",
        keyword="ゴミ袋 半透明",
        name_hints=("ゴミ袋", "ごみ袋"),
        genre_id="100939",
        scene="ゴミの日の朝に指定袋がないとき",
        problem="朝の出発が遅れ、最悪ゴミを一週間持ち越す",
        benefit="指定サイズを先に積んでおけば、朝の慌てと持ち越しが消える",
        buy_reason="ゴミ袋切れは時間も気力も持っていく",
        avoid="自治体の色・厚さ指定を見落とさない",
        template_id="hook-benefit",
    ),
    PainIntent(
        id="water-case",
        pain="水、まだ店で抱えて帰ってる？",
        keyword="天然水 ラベルレス",
        name_hints=("天然水", "ラベルレス", "ミネラルウォーター"),
        genre_id="100227",
        scene="買い出し帰りが重くてしんどい日",
        problem="重い水を運ぶたびに疲れが残り、他の家事まで崩れる",
        benefit="ケース水を宅配に寄せれば、腕も時間も空けて帰宅できる",
        buy_reason="水は「買う商品」より「運ばなくていい仕組み」",
        avoid="置き場所（箱の高さ）を測ってから決める",
        template_id="hook-benefit",
    ),
    PainIntent(
        id="wrap",
        pain="ラップ、引き出しの奥で切れかけてない？",
        keyword="サランラップ",
        name_hints=("サランラップ", "食品用ラップ", "ラップフィルム"),
        genre_id="551167",
        scene="お弁当や作り置きの朝",
        problem="朝いちで切れると準備が止まり、出発が全体的に遅れる",
        benefit="替え玉があれば朝の小パニックが消え、支度が止まらない",
        buy_reason="朝に効く消耗品は、前夜の自分への投資",
        avoid="幅（22cm/30cm）の取り違えに注意",
        template_id="hook-benefit",
    ),
    PainIntent(
        id="dish-sponge",
        pain="スポンジ、ヌメってきたら替え時だよ",
        keyword="キッチンスポンジ 抗菌",
        name_hints=("キッチンスポンジ", "食器洗いスポンジ", "スポンジたわし"),
        genre_id="551167",
        scene="洗い物のたびに衛生感が気になるとき",
        problem="替え時を逃すと気持ち悪さと洗い残し不安が毎日続く",
        benefit="まとめ買いしておけば迷わず交換でき、洗い物のストレスが下がる",
        buy_reason="安い消耗品ほど、決断コストをゼロにする価値がある",
        avoid="油汚れ用とグラス用を分けた方が持ちがいい",
        template_id="hook-benefit",
    ),
    PainIntent(
        id="dishwasher-tab",
        pain="食洗機の洗剤、残り少なくない？",
        keyword="食洗機 洗剤 タブレット",
        name_hints=("食洗機用", "食器洗い機用", "食洗機洗剤", "食洗機用洗剤"),
        genre_id="551167",
        scene="食洗機を回すたびに減っていくストック",
        problem="切れると手洗い戻りが発生し、共働きの夜が一気に重くなる",
        benefit="大容量を先に置けば買い忘れが減り、時短家電が止まらない",
        buy_reason="食洗機は洗剤があって初めて時短装置になる",
        avoid="機種の専用指定（粉/タブ/ジェル）を確認",
        template_id="hook-benefit",
    ),
    PainIntent(
        id="kitchen-paper",
        pain="キッチンペーパー、料理中に切れたことない？",
        keyword="キッチンペーパー",
        name_hints=("キッチンペーパー", "クッキングペーパー"),
        genre_id="551167",
        scene="揚げ物や肉の下処理の最中",
        problem="調理中に切れると手が止まり、油跳ねや片付けが雑になる",
        benefit="替えが1個あるだけで調理が止まらず、後片付けも楽になる",
        buy_reason="料理中の切れは、いちばん腹立たしい切れ方",
        avoid="ホルダーサイズに合うかだけ先に見る",
        template_id="hook-benefit",
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

# うち2枠は「30代共働きのリアル苦悩」投稿（攻略ネタではなく共感系）。
# 12:00 昼休み / 21:00 夜のひと息。
STRUGGLE_SLOTS: Tuple[int, ...] = (2, 8)

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
