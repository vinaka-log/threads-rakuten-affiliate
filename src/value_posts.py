"""価値投稿（リンクなし・保存されるネタ）のプールとローテーション。

紹介投稿の間に「役に立つ・保存したくなる」投稿を挟むことで
アルゴリズム評価と信頼を積む。リンク・#PRは一切入れない。

ペルソナ A（家庭の消耗品・時短買い）向け:
  ストック補充・重い日用品の宅配・ポイント日のまとめ買いが主語。
  共感つぶやき（STRUGGLE_SLOTS）と、テーマ無関係の雑談（CHITCHAT_SLOTS）を混ぜる。
  攻略ネタは tip 枠のみ。

1日に config.VALUE_SLOTS の数だけ静的投稿が出る。
tip / struggle / chitchat で別プールをローテする。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

import config
from sale import active_sale_label


@dataclass(frozen=True)
class ValuePost:
    value_id: str
    text: str


# 各投稿の方針:
#   - 1行目は42文字以内のフック（家庭のあるある・断言）
#   - 保存したくなる具体情報を入れる
#   - 最後は問いかけで締めて返信を促す
#   - シロクマの脱力・正直トーンで統一
#   - 変わりやすい制度の数値（SPU倍率等）は書かない
#   - 主語は「家庭の買い足し担当」に寄せる（美容・ガジェットは扱わない）
_POOL: Sequence[ValuePost] = (
    # --- 楽天攻略系 ---
    ValuePost(
        "zero-five-basics",
        "楽天で買う日、適当に決めてない?\n\n"
        "しろくま的には「5と0のつく日」が基本🐻‍❄️\n"
        "毎月5・10・15・20・25・30日は\n"
        "楽天カード払いでポイントアップ。\n\n"
        "エントリーが毎回必要なのだけ注意ね。\n"
        "急ぎじゃないものはカゴに入れて寝かせておくと\n"
        "この日にまとめて買えるよ。\n\n"
        "みんなは買う日、決めてる派？",
    ),
    ValuePost(
        "marathon-basics",
        "お買い物マラソン、仕組み分かってない人が意外と多い\n\n"
        "ざっくり言うと「買い回り」🐻‍❄️\n"
        "・1,000円以上の買い物を別ショップでするたび倍率+1倍\n"
        "・最大10ショップで+9倍\n"
        "・上限ポイントがあるので買いすぎ注意\n\n"
        "コツは、日用品や消耗品を1,000円ちょっとで\n"
        "小分けに買って倍率を稼ぐこと。\n\n"
        "マラソン、毎回参加してる？",
    ),
    ValuePost(
        "marathon-x-05",
        "マラソン中の「5と0のつく日」、実は最強の日\n\n"
        "買い回りの倍率と\n"
        "5と0のつく日のポイントアップが重なるから、\n"
        "しろくまは大物をこの日に寄せてる🐻‍❄️\n\n"
        "セール期間に入ったらカレンダーを見て、\n"
        "5・10・15・20・25・30日が挟まってないか確認してみて。\n\n"
        "大きい買い物、タイミング計算してる？",
    ),
    ValuePost(
        "gessho-entry",
        "月が変わったらまずやること、あるよ🐻‍❄️\n\n"
        "楽天はエントリー制のキャンペーンが多いから、\n"
        "月初に一度キャンペーンページを見て\n"
        "ポチポチしておくのがおすすめ。\n\n"
        "エントリーし忘れて対象外、が\n"
        "いちばんもったいないやつだから…\n\n"
        "月初ルーティン、なにかある？",
    ),
    ValuePost(
        "spu-check",
        "「同じ買い物なのにポイント差がつく」理由の多くはSPU\n\n"
        "楽天のサービスをどれだけ使ってるかで\n"
        "もらえる倍率が変わる仕組み🐻‍❄️\n\n"
        "倍率や条件はちょくちょく変わるから、\n"
        "数字は公式ページで確認するのが確実。\n"
        "無理に全部埋めるより「もう使ってるサービスだけ」で十分だよ。\n\n"
        "SPU、意識してる？してない？",
    ),
    ValuePost(
        "furusato",
        "ふるさと納税、楽天でやると気づくこと\n\n"
        "寄付も通常の買い物と同じように\n"
        "ポイントの対象になる場合があるんだよね🐻‍❄️\n"
        "（キャンペーン条件は都度確認してね）\n\n"
        "どうせやるなら、セールや買い回りと\n"
        "重ねるのがしろくま流。\n\n"
        "ふるさと納税、もう今年の分やった？",
    ),
    ValuePost(
        "coupon-search",
        "同じ商品、クーポンの有無で数百円変わることある\n\n"
        "買う前の10秒チェック🐻‍❄️\n"
        "・商品ページの価格の下にクーポン表示がないか見る\n"
        "・「ショップ名 クーポン」で楽天内検索\n"
        "・楽天のクーポンページ（RaCoupon）をのぞく\n\n"
        "取得ボタンを押し忘れて定価で買うの、\n"
        "いちばん悲しいやつだから気をつけて。\n\n"
        "クーポン確認、毎回してる？",
    ),
    ValuePost(
        "39-shop",
        "送料で損してる人、まだいる気がする\n\n"
        "楽天は「39ショップ」って表示がある店なら\n"
        "3,980円以上で送料無料🐻‍❄️\n\n"
        "あとちょっとで届かないときは\n"
        "どうせ使う消耗品（洗剤・ラップ・水）を\n"
        "足すのがいちばん無駄がないよ。\n\n"
        "送料調整用の「いつもの1品」、何にしてる？",
    ),
    ValuePost(
        "limited-points",
        "期間限定ポイント、失効させたことない?\n\n"
        "しろくまの使い切り先🐻‍❄️\n"
        "・楽天ペイでコンビニ・ドラッグストア払い\n"
        "・楽天モバイル/楽天でんきの支払いに充当\n"
        "・日用品のストック買い\n\n"
        "ポイントで通常の買い物を置き換えて、\n"
        "浮いた現金を貯金に回すのが正解だと思ってる。\n\n"
        "期間限定ポイント、何に使ってる？",
    ),
    ValuePost(
        "point-math",
        "「ポイント10倍」って結局いくら得か即答できる?\n\n"
        "ざっくり計算🐻‍❄️\n"
        "・10倍 = 実質10%引きくらいの感覚\n"
        "・3,000円の買い物なら300ポイント\n"
        "・ただし期間限定ポイントのことが多いので使い道までセットで考える\n\n"
        "「倍率が高い日に、どうせ買うものを買う」\n"
        "これだけで年間だと結構変わるよ。\n\n"
        "ポイント、年間いくら貯まってるか把握してる？",
    ),
    ValuePost(
        "favorite-notify",
        "欲しいものを定価で買うの、ちょっと待って\n\n"
        "楽天は「お気に入り登録」しておくと\n"
        "値下げやクーポンの通知が来ることがある🐻‍❄️\n\n"
        "しろくまは急がないものは全部お気に入りに入れて、\n"
        "通知が来たときとセール日を比べて買ってる。\n\n"
        "「待てば安くなる」を仕組み化すると楽だよ。\n\n"
        "お気に入り登録、活用してる？",
    ),
    ValuePost(
        "keep-cart",
        "「カゴに入れて寝かせる」って技、知ってる?\n\n"
        "欲しいものはすぐ買わずに買い物かごへ🐻‍❄️\n\n"
        "・衝動買いのクールダウンになる\n"
        "・セール日にまとめて精算できる\n"
        "・数日経って「やっぱいらない」が結構ある\n\n"
        "カゴは無料の「考える時間」だと思ってる。\n\n"
        "いまカゴに何個入ってる？",
    ),
    # --- レビュー・買い方の目利き系 ---
    ValuePost(
        "review-reading",
        "レビュー4.5点を鵜呑みにして失敗したことある?\n\n"
        "しろくまのレビューの読み方🐻‍❄️\n"
        "・点数より件数を先に見る（100件未満は参考程度）\n"
        "・★1〜2から読む。不満の共通点が本当の弱点\n"
        "・「リピしてます」が多い商品は強い\n"
        "・直近のレビューを見る（仕様変更で別物のことがある）\n\n"
        "低評価から読むの、やってる人いる？",
    ),
    ValuePost(
        "review-sakura",
        "「怪しいレビュー」の見分け方、まとめとくね🐻‍❄️\n\n"
        "・短期間に★5が集中している\n"
        "・文面がどれも似ていて具体性がない\n"
        "・商品と関係ない褒め言葉が多い\n"
        "・★5と★1に極端に割れている\n\n"
        "逆に「ここが惜しい」って書いてある★4は\n"
        "いちばん信用できると思ってる。\n\n"
        "レビューで「これは怪しい」って思った経験ある？",
    ),
    ValuePost(
        "shop-review",
        "商品レビューとショップレビュー、両方見てる?\n\n"
        "商品が良くても、お店の対応が微妙なことはある🐻‍❄️\n\n"
        "・発送が遅い\n"
        "・問い合わせの返事が来ない\n"
        "・梱包が雑\n\n"
        "こういうのはショップレビューに出るから、\n"
        "高い買い物のときは両方チェックが安心だよ。\n\n"
        "ショップレビューまで見る派？",
    ),
    ValuePost(
        "ranking-howto",
        "楽天ランキング、実は種類があるの知ってた?\n\n"
        "・リアルタイム: いま瞬間的に売れてるもの\n"
        "・デイリー: その日ちゃんと売れたもの\n"
        "・週間: 安定して売れ続けてるもの\n\n"
        "しろくまが毎日見てるのはデイリー🐻‍❄️\n"
        "瞬間風速じゃなくて「ちゃんと選ばれてるもの」が分かるから。\n\n"
        "ランキング見る習慣ある人いる？",
    ),
    ValuePost(
        "ranking-trap",
        "ランキング1位=自分に合う、とは限らないんだよね\n\n"
        "1位はセールやテレビの影響で\n"
        "瞬間的に入れ替わることも多い🐻‍❄️\n\n"
        "しろくまは「上位に居座り続けてる商品」を信用してる。\n"
        "何週間も上位にいるのは、リピーターがいる証拠だから。\n\n"
        "流行りで買って失敗したこと、ある？",
    ),
    ValuePost(
        "size-check",
        "ネット通販の失敗、だいたい「サイズ」じゃない?\n\n"
        "しろくまの対策🐻‍❄️\n"
        "・商品写真は大きく見えると心得る\n"
        "・寸法をメモしてメジャーで実際に測る\n"
        "・置き場所の幅・奥行き・高さを先に測る\n"
        "・服はレビューの「身長・体重」記載を探す\n\n"
        "メジャー1本で失敗がかなり減るよ。\n\n"
        "サイズ失敗、最近やった？",
    ),
    ValuePost(
        "shipping-check",
        "「あす楽」表示、ちゃんと見てから買ってる?\n\n"
        "急ぎのものは商品ページの\n"
        "お届け目安と発送元をチェック🐻‍❄️\n\n"
        "・「あす楽」対応なら最短翌日\n"
        "・受注生産や取り寄せは日数がかかる\n"
        "・土日をはさむと想定よりずれる\n\n"
        "プレゼントは特に余裕を持ってね。\n\n"
        "配送で焦った経験、ある？",
    ),
    ValuePost(
        "double-price",
        "「セールで半額!」を見たときの、ひと呼吸🐻‍❄️\n\n"
        "元の価格が本当にその値段だったか、\n"
        "他の店の相場はどうかを軽く見てからでも遅くない。\n\n"
        "・同じ商品名で楽天内検索して比較\n"
        "・普段の価格帯を知ってるものから買う\n\n"
        "「割引率」じゃなくて「支払う金額」で判断するのがコツ。\n\n"
        "半額表示、つい反応しちゃわない？",
    ),
    ValuePost(
        "regret-checklist",
        "ポチる前のしろくまチェックリスト🐻‍❄️\n\n"
        "・レビュー件数100件以上ある?\n"
        "・★1レビューの不満は自分に関係ある?\n"
        "・サイズ/容量、ちゃんと見た?（写真は大きく見える）\n"
        "・同じ店の類似品と価格比べた?\n"
        "・今日買う理由ある?（セール/ポイント日）\n\n"
        "全部YESなら、たぶん後悔しないよ。\n\n"
        "みんなの「買う前ルール」あったら教えて",
    ),
    ValuePost(
        "stock-buy",
        "日用品を定価で買うの、そろそろやめない?\n\n"
        "しろくま式ストック買い🐻‍❄️\n"
        "・洗剤/柔軟剤/歯磨き粉は無くなる前にセールで補充\n"
        "・水とお米は重いから楽天で届けてもらう\n"
        "・買い回りの1,000円枠にちょうどいい\n\n"
        "ドラッグストアで都度買うより、\n"
        "セール日にまとめる方がポイント分だけ確実に得。\n\n"
        "楽天で定期的に買ってる日用品ある？",
    ),
    ValuePost(
        "heavy-items",
        "「重いものはネットで買う」を徹底したら生活変わった\n\n"
        "しろくまが楽天に任せてるもの🐻‍❄️\n"
        "・水、お米、ペットボトル飲料\n"
        "・洗剤の詰め替え大容量\n"
        "・ティッシュ、トイレットペーパー\n\n"
        "スーパーで重い袋を運ぶ労力、\n"
        "ぜんぶ配達員さんにお願いしていいんだよ…\n\n"
        "「これはもう店で買わない」ってもの、ある？",
    ),
    ValuePost(
        "budget-rule",
        "月の「楽天予算」って決めてる?\n\n"
        "しろくまのゆるいルール🐻‍❄️\n"
        "・日用品と食品は予算内で自由\n"
        "・1万円超えの買い物は3日寝かせる\n"
        "・セールだからという理由だけでは買わない\n\n"
        "「安く買う」より「いらないものを買わない」方が\n"
        "節約効果は大きいんだよね。\n\n"
        "買い物のマイルール、なにかある？",
    ),
    # --- 雑談・問いかけ系 ---
    ValuePost(
        "chat-repeat",
        "みんなが楽天で「リピしてるもの」が知りたい🐻‍❄️\n\n"
        "しろくまは毎日ランキングを見てるけど、\n"
        "ランキングに出てこない「静かな定番」って\n"
        "絶対あると思うんだよね。\n\n"
        "水でも洗剤でもお菓子でもなんでもOK。\n"
        "「これはもう3回買ってる」ってやつ、\n"
        "リプで教えてくれたらうれしいな。",
    ),
    ValuePost(
        "chat-cart-now",
        "いま買い物かごに入ってるもの、言える?🐻‍❄️\n\n"
        "しろくまのカゴには\n"
        "「いつか買う」が数件眠ってる…\n\n"
        "カゴの中身って、その人の生活が見えて\n"
        "ちょっとおもしろいんだよね。\n\n"
        "差し支えなければ、カゴに入れっぱなしのもの\n"
        "リプで教えて。背中を押すか止めるかするよ",
    ),
    ValuePost(
        "chat-gohobi",
        "「自分へのご褒美」って何買ってる?🐻‍❄️\n\n"
        "がんばった週の金曜日、\n"
        "ちょっといいおやつをポチるのが\n"
        "しろくまの密かな楽しみ。\n\n"
        "高くなくていいんだよね。\n"
        "「これがあると機嫌よく過ごせる」ってものがあると強い。\n\n"
        "みんなのご褒美、参考にしたいから教えて",
    ),
    ValuePost(
        "chat-hidden-gem",
        "「有名じゃないけど神」って商品に出会ったことある?\n\n"
        "CMもしてない、インフルエンサーも紹介してない、\n"
        "でもレビューだけ異様に熱い…みたいなやつ🐻‍❄️\n\n"
        "そういう「隠れ名品」を見つけたときが\n"
        "ネットショッピングでいちばん楽しい瞬間だと思う。\n\n"
        "あなたの隠れ名品、こっそり教えて",
    ),
    ValuePost(
        "chat-first-buy",
        "楽天で最初に買ったもの、覚えてる?🐻‍❄️\n\n"
        "しろくまは覚えてないんだけど、\n"
        "気づいたら購入履歴がすごい長さになってた…\n\n"
        "購入履歴って自分の生活の記録みたいで、\n"
        "たまに見返すとおもしろいよ。\n\n"
        "「初めて買ったもの」か「いちばん古い履歴」、\n"
        "見てみて教えてくれない？",
    ),
    ValuePost(
        "chat-use-up",
        "「使い切ったら絶対また買う」ってもの、ある?🐻‍❄️\n\n"
        "本当に良いものって、\n"
        "SNSでバズってるものじゃなくて\n"
        "静かに何回も買われてるものだと思うんだ。\n\n"
        "しろくまはそういう「無言のリピート」を\n"
        "いちばん信用してる。\n\n"
        "あなたの無言リピート品、教えて",
    ),
    ValuePost(
        "chat-timing",
        "ネットで買い物するの、何時が多い?🐻‍❄️\n\n"
        "しろくま調べだと、夜ふかし中のポチりは\n"
        "翌朝「なんで買ったんだろ」率が高め…\n\n"
        "でも夜のほうがゆっくり選べるのも分かる。\n"
        "カゴに入れて翌朝決済が平和かもしれない。\n\n"
        "夜ポチ派？ 昼ポチ派？",
    ),
    # --- 失敗談系 ---
    ValuePost(
        "fail-story",
        "しろくま、先月やらかした話していい?\n\n"
        "セールで安くなってた収納ケース、\n"
        "サイズをよく見ずにポチったら\n"
        "思ってたのの半分くらいの大きさだった…🐻‍❄️\n\n"
        "写真って大きく見えるんだよね。\n"
        "それ以来、寸法をメジャーで測ってから買ってる。\n\n"
        "「安さに釣られて失敗したもの」ある?\n"
        "リプで供養しよ",
    ),
    ValuePost(
        "fail-coupon",
        "クーポン、取得したつもりで取得してなかった話\n\n"
        "この前、クーポン対象の商品を買って\n"
        "「安く買えた」と思ってたら、\n"
        "取得ボタンを押してなくて定価だった…🐻‍❄️\n\n"
        "クーポンは「表示されてる」だけじゃだめで\n"
        "「取得して」「条件を満たして」初めて効くからね。\n\n"
        "同じことやった人、いる…?",
    ),
    ValuePost(
        "fail-shipping",
        "合計金額を見ずにポチって、送料で泣いた話\n\n"
        "商品価格だけ見て「安い!」と思ったら\n"
        "送料が商品の半額くらいした…🐻‍❄️\n\n"
        "それ以来、しろくまは\n"
        "「送料込みの支払額」で他の店と比べるようにしてる。\n"
        "39ショップの送料無料ラインも忘れずに。\n\n"
        "送料で「うっ」となった経験、ある？",
    ),
    ValuePost(
        "fail-double",
        "同じものを2回買った話、聞いて…🐻‍❄️\n\n"
        "ストックがあるのを忘れて\n"
        "洗剤の詰め替えをまた買ってしまった。\n"
        "（まあ、いつか使うからいいんだけど…）\n\n"
        "それ以来、ストック棚の写真を\n"
        "スマホに撮ってから買い物するようにしてる。\n"
        "これ、地味に効くよ。\n\n"
        "ダブり買い、やったことある？",
    ),
    ValuePost(
        "kuma-intro",
        "はじめましての人も増えたので、自己紹介🐻‍❄️\n\n"
        "共働きの「また切れた…」を減らすしろくまです。\n"
        "・日用品とキッチンの売れ筋を毎日メモ\n"
        "・重いもの・ストック補充の買い時を伝える\n"
        "・ポイント日やセールの目安も流す\n"
        "・紹介にはPR（アフィリエイトリンク）を含みます\n\n"
        "ドラッグストア往復、もう一回減らしたい人向け。\n\n"
        "フォローのきっかけ、よかったら教えて",
    ),
)

# 30代共働きのリアル苦悩（リンクなし・PRなし）。
# STRUGGLE_SLOTS（1日7本）専用。
# 書き方:
#   - 友達に送る愚痴くらいの口語。きれいな起承転結にしない
#   - 具体物（冷凍パスタ、牛乳、指定袋）を入れる
#   - 「学び」「比喩」「まとめ」で締めない。気になって聞く感じで終わる
#   - URLなし / ハート絵文字なし
#   - AIっぽい言い回し禁止例: クエスト / 在庫管理ゲー / ヒーローイベント / 可視化
_STRUGGLE_POOL: Sequence[ValuePost] = (
    ValuePost(
        "struggle-dinner-war",
        "共働きの夜ご飯って難しいよね…\n\n"
        "昼は冷凍パスタで済ませちゃうけど、\n"
        "夜はちゃんと作ろうっ気持ちと\n"
        "スーパーに行くのが面倒くさい気持ちが戦ってる😂\n\n"
        "結局お惣菜にしちゃうけど、\n"
        "共働き夫婦は夜ご飯どうしてるのか気になる…",
    ),
    ValuePost(
        "struggle-empty-fridge",
        "帰って冷蔵庫開けたら、\n"
        "ドレッシングと卵しかなくて夫婦で無言になった…\n\n"
        "外食行く？って言えばいいのに\n"
        "なんか言えなくて、コンビニ行って終わった😂\n\n"
        "こういう夜、うちだけ？",
    ),
    ValuePost(
        "struggle-who-buys",
        "トイレットペーパー、いつも気づくの私なんだけど\n"
        "旦那は芯まで行ってから「あ、切れてる」って言うのやめてほしい\n\n"
        "怒ってるというより、なんで毎回私なんだろうってなる\n\n"
        "消耗品、気づくの偏ってる家ある？",
    ),
    ValuePost(
        "struggle-drugstore-overtime",
        "残業終わりなのに\n"
        "洗剤切れてるの思い出してマツキヨ寄った…\n\n"
        "牛乳と柔軟剤だけ持って帰宅するの、\n"
        "なんか負けた感じする😂\n\n"
        "帰りの寄り道、みんな何買ってる？",
    ),
    ValuePost(
        "struggle-weekend-errands",
        "休日なのに朝から買い出し行って、\n"
        "帰ってきたらダンボール開けて、\n"
        "洗い物して、気づいたら夕方だった\n\n"
        "休みどこいった…\n\n"
        "日曜ってみんな何してるの？",
    ),
    ValuePost(
        "struggle-mental-stock",
        "会議中なのに急に\n"
        "柔軟剤あと何回分だっけ？って浮かんで困る\n\n"
        "米いつ頼んだかも忘れてるし\n"
        "今晚のおかず足りるかも不安\n\n"
        "頭の中ずっと買い物リストになってる人いる？",
    ),
    ValuePost(
        "struggle-delivery-box",
        "宅配ボックスパンパンで\n"
        "玄関がダンボールだらけなんだけど…\n\n"
        "ネットで買うと楽なのは分かる。\n"
        "開けるのと捨てるの誰がやる問題だけ残る😂\n\n"
        "ダンボール、すぐ畳めてる人尊敬する",
    ),
    ValuePost(
        "struggle-night-cart",
        "夜中に楽天開いてカートに入れて、\n"
        "レビューずっと読んで、\n"
        "結局買わずに寝た\n\n"
        "明日買うって自分に言ってるけど\n"
        "たぶんまた同じことする😂\n\n"
        "カート放置、何個ある？",
    ),
    ValuePost(
        "struggle-point-guilt",
        "5のつく日忘れて普通に買っちゃった…\n\n"
        "数百円の差なのに、なんか損した気分が消えない\n"
        "忙しい日ほどポイント意識できなくて自己嫌悪\n\n"
        "みんなポイント日、ちゃんと覚えてる？",
    ),
    ValuePost(
        "struggle-both-tired",
        "「今日スーパー寄れる？」ってLINEしたら\n"
        "既読で返信なくて、こっちも無理って分かった\n\n"
        "結局ふたりともコンビニでお茶とパン買って帰った😂\n\n"
        "似たこと、あるある？",
    ),
    ValuePost(
        "struggle-invisible-work",
        "洗剤買って、開封して、詰め替えて、\n"
        "空のボトル捨てて、次いつ切れるか覚える\n\n"
        "これ誰の仕事なんだろうって思うことある\n"
        "やらないと止まるのに、やってる感ないのつらい\n\n"
        "うち、こういうの誰がやってる？",
    ),
    ValuePost(
        "struggle-salary-day",
        "給料入った瞬間は安心するのに、\n"
        "家賃と保育料と日用品で\n"
        "すぐいつもの残高に戻るの何…\n\n"
        "贅沢してないのに残らないの、静かにくる\n\n"
        "最近値上げでキツくなったものある？",
    ),
    ValuePost(
        "struggle-morning-out",
        "朝、ティッシュ箱から最後の1枚出て\n"
        "出勤前に「やっば」ってなった\n\n"
        "昨日の夜気づいてたのに動けなかったやつ\n"
        "またやった…\n\n"
        "朝の消耗品切れ、あるあるすぎない？",
    ),
    ValuePost(
        "struggle-compare",
        "インスタの共働き家庭、玄関きれいすぎて\n"
        "うちの靴とダンボールと明日の袋が急に恥ずかしくなる\n\n"
        "回ってるだけなのに負けた気分になるのやめてほしい😂\n\n"
        "最近見て凹んだ投稿ある？",
    ),
    ValuePost(
        "struggle-tiny-win",
        "今日いちばんの勝利、\n"
        "柔軟剤切れそうなのに先に買えたこと\n\n"
        "小さいけど、朝慌てなくて済むやつ\n\n"
        "地味な勝ち報告、なんかある？",
    ),
    ValuePost(
        "struggle-dinner-side-dish",
        "肉焼けた。で、野菜どうする問題が残る…\n\n"
        "袋サラダ？冷凍のブロッコリー？昨日の残り？\n"
        "ここで5分悩むのがいちばんしんどい😂\n\n"
        "平日の副菜、みんな何にしてる？",
    ),
    ValuePost(
        "struggle-frozen-guilt",
        "今日も冷凍で済ませた\n\n"
        "普通にうまいし時短なのに、\n"
        "ちゃんとしてない感だけ残るのなんで…\n\n"
        "共働きなんだからいいじゃんって思うけど\n"
        "頭の中の理想の夜ご飯がうるさい\n\n"
        "冷凍罪悪感、ある派？ない派？",
    ),
    ValuePost(
        "struggle-what-to-eat",
        "「今日ごはん何？」が\n"
        "一日でいちばん重い質問すぎる\n\n"
        "仕事の判断はまだできるのに\n"
        "献立だけ急に脳死する😂\n\n"
        "夫婦でこれ聞いてゲンナリする家、ある？",
    ),
    ValuePost(
        "struggle-late-home-dinner",
        "21時半帰宅だと\n"
        "もう料理というより今夜を終わらせたい気持ち\n\n"
        "洗い物増やしたくないし眠い\n"
        "でもカップ麺だけはなんか避けたくなる\n\n"
        "遅い日のご飯、何食べてる？",
    ),
    ValuePost(
        "struggle-bento-morning",
        "お弁当、愛情とか言ってる場合じゃなくて\n"
        "冷凍焼きおにぎりと昨日の残りとプチトマトで締めた\n\n"
        "彩りとか無理。空っぽだけは避けたい\n\n"
        "みんな朝弁当どこまで作ってる？",
    ),
    ValuePost(
        "struggle-milk-again",
        "なんで牛乳だけいつも切れるの\n\n"
        "洗剤はストックあるのに、\n"
        "朝のコーヒーのタイミングで卵と牛乳がないの判明する\n\n"
        "うちだけ？よく切れるものある？",
    ),
    ValuePost(
        "struggle-trash-day",
        "ゴミの日なのに指定袋がないと\n"
        "朝から詰む…\n\n"
        "昨日買えばよかった案件、\n"
        "だいたい昨日の夜には思い出せない😂\n\n"
        "ゴミ関連で焦った人、最近いる？",
    ),
    ValuePost(
        "struggle-laundry-pile",
        "洗濯カゴやばいのに\n"
        "柔軟剤の残量怪しくて回せない\n\n"
        "回したい。でも足りないと分かると止まる\n\n"
        "洗濯、途中で止まってることある？",
    ),
    ValuePost(
        "struggle-weekend-meal-prep",
        "週末作り置きしようと思って\n"
        "野菜だけ買って満足してしまった\n\n"
        "調理は来週の自分へ丸投げ済み😂\n\n"
        "作り置き、何日続いてる？正直に教えて",
    ),
    ValuePost(
        "struggle-delivery-dinner",
        "デリバリー開いて値段見て閉じる\n"
        "また開く。また閉じる\n\n"
        "高い。でも作る気力ない。\n"
        "惣菜取りに出るのも面倒\n\n"
        "結局頼んで配達時間見て安心するやつ\n\n"
        "デリバリー週何回くらい？",
    ),
    ValuePost(
        "struggle-kids-leftover",
        "子どもの食べ残し見て\n"
        "自分の夜ご飯決めるの、地味に悩む\n\n"
        "残ったうどんアレンジするか、\n"
        "大人だけ別にするか…\n\n"
        "もったいない気持ちと、自分もいいもの食べたい気持ち\n\n"
        "残りものどうしてる？",
    ),
    ValuePost(
        "struggle-supermarket-crowd",
        "仕事終わりのスーパー混みすぎて\n"
        "入った瞬間帰る気になった\n\n"
        "カートないしレジ長いし、\n"
        "卵とネギだけなのに疲れる😂\n\n"
        "夕方スーパー、まだ行ってる派？",
    ),
    ValuePost(
        "struggle-same-menu",
        "今週の夜ご飯また\n"
        "カレー→丼→パスタ→炒め物だった\n\n"
        "安定はしてる。飽きたかも…\n"
        "でも新しいレシピ見る気力がない\n\n"
        "うちの鉄板、なにが多い？",
    ),
    ValuePost(
        "struggle-tired-talk",
        "帰ってきて最初の会話、\n"
        "だいたい「疲れたね」で始まる\n\n"
        "仕事の話する元気もないし、\n"
        "黙ってるのもなんか変\n\n"
        "みんな帰宅後の第一声なに？",
    ),
    ValuePost(
        "struggle-morning-rush-food",
        "朝ごはん食べる？あと5分寝る？\n"
        "毎日これで悩んでる\n\n"
        "結局コーヒーとチョコパンで終わる\n\n"
        "平日の朝ごはん、何食べてる？",
    ),
    ValuePost(
        "struggle-receipt-stack",
        "財布の中のレシート増えすぎ問題\n\n"
        "家計簿つけようとは思う。\n"
        "仕分けする夜が来ない😂\n\n"
        "気づいたら「これ何のレシート」だらけ\n\n"
        "家計、いつ振り返ってる？",
    ),
    ValuePost(
        "struggle-rain-errand",
        "雨の日に限って牛乳切れるのやめてほしい\n\n"
        "電池もないし、濡れながらコンビニ行った\n"
        "前もって買える人、どうやって気づいてるの…\n\n"
        "雨の日買い出し、あるある？",
    ),
    ValuePost(
        "struggle-fridge-mystery",
        "冷蔵庫の奥から\n"
        "いつ買ったか分からない納豆出てきた…\n\n"
        "買うときは絶対使う気満々なのに\n"
        "気づいたら期限ギリギリor切れ\n\n"
        "最近こっそり捨てた食材、ある？",
    ),
    ValuePost(
        "struggle-weekday-bath",
        "帰ってきて\n"
        "風呂？ご飯？洗い物？の順番決めから始まる\n\n"
        "正解ないのに、決めないと動かないのつらい\n\n"
        "帰宅後の定番ルート、決まってる？",
    ),
    ValuePost(
        "struggle-sunday-anxiety",
        "日曜の夕方なのに\n"
        "もう月曜の買い物リスト考えてる…\n\n"
        "洗剤、弁当のパン、提出物…\n"
        "休む前から次の週が始まるの嫌だ\n\n"
        "日曜夜そわそわする人、いる？",
    ),
)


# 雑談本文は data/chitchat_pool.json（自動補充あり）。
# CHITCHAT_SLOTS（1日2本）。一度投稿したら台帳で消費し二度と使わない。



def pool() -> Sequence[ValuePost]:
    return _POOL


def struggle_pool() -> Sequence[ValuePost]:
    return _STRUGGLE_POOL


def chitchat_pool() -> Sequence[ValuePost]:
    """data/chitchat_pool.json から雑談を読む（自動生成分も含む）。"""
    from chitchat_gen import load_pool

    out: list[ValuePost] = []
    for row in load_pool().get("items") or []:
        if not isinstance(row, dict):
            continue
        vid = str(row.get("id") or "").strip()
        text = str(row.get("text") or "").strip()
        if vid and text:
            out.append(ValuePost(vid, text))
    return out


def _chitchat_ids() -> set[str]:
    return {p.value_id for p in chitchat_pool()}


def used_chitchat_ids(ledger_path: Path | None = None) -> set[str]:
    """台帳に一度でも載った雑談ID（二度と使わない）。"""
    from picker import load_ledger

    path = ledger_path or config.LEDGER_PATH
    known = _chitchat_ids()
    used: set[str] = set()
    for e in load_ledger(path):
        code = str(e.get("item_code") or "")
        kind = str(e.get("kind") or "")
        if not code.startswith("value:"):
            continue
        vid = code.split(":", 1)[-1]
        if vid in known or kind == "chitchat" or vid.startswith("chat-auto-"):
            used.add(vid)
    return used


def unused_chitchat_posts(ledger_path: Path | None = None) -> list[ValuePost]:
    used = used_chitchat_ids(ledger_path)
    return [p for p in chitchat_pool() if p.value_id not in used]


def is_chitchat_id(value_id: str) -> bool:
    if value_id.startswith("chat-auto-"):
        return True
    return value_id in _chitchat_ids()


def _non_tip_slots() -> tuple[int, ...]:
    return tuple(config.STRUGGLE_SLOTS) + tuple(getattr(config, "CHITCHAT_SLOTS", ()) or ())


def _struggle_position(slot: int) -> int:
    """その日の苦悩枠のうち何番目か（0始まり）。"""
    if slot in config.STRUGGLE_SLOTS:
        return config.STRUGGLE_SLOTS.index(slot)
    return 0


def _chitchat_position(slot: int) -> int:
    slots = tuple(getattr(config, "CHITCHAT_SLOTS", ()) or ())
    if slot in slots:
        return slots.index(slot)
    return 0


def _static_position(slot: int) -> int:
    """その日の攻略系価値枠のうち何番目か（0始まり）。"""
    tip_slots = tuple(s for s in config.VALUE_SLOTS if s not in _non_tip_slots())
    if slot in tip_slots:
        return tip_slots.index(slot)
    if slot in config.VALUE_SLOTS:
        return config.VALUE_SLOTS.index(slot)
    return slot % max(1, len(config.VALUE_SLOTS))


def _pick_chitchat(on: date, slot: int) -> ValuePost:
    """雑談は一度きり。足りなければ自動補充してから未使用を選ぶ。"""
    try:
        from chitchat_gen import ensure_chitchat_supply

        ensure_chitchat_supply()
    except Exception as exc:
        print(f"WARNING: chitchat refill failed: {exc}", flush=True)

    unused = unused_chitchat_posts()
    if not unused:
        print(
            "WARNING: chitchat pool exhausted; falling back to struggle post.",
            flush=True,
        )
        k = 0
        idx = (on.toordinal() * max(1, len(config.STRUGGLE_SLOTS)) + k) % len(_STRUGGLE_POOL)
        return _STRUGGLE_POOL[idx]
    k = _chitchat_position(slot)
    slots_n = max(1, len(getattr(config, "CHITCHAT_SLOTS", ()) or (0,)))
    idx = (on.toordinal() * slots_n + k) % len(unused)
    return unused[idx]


def pick_value_post(on: date, slot: int = 0) -> ValuePost:
    """日付×枠ローテで価値投稿を1本選ぶ。

    STRUGGLE_SLOTS → 共働きリアル苦悩
    CHITCHAT_SLOTS → テーマ無関係の雑談（一度きり・自動補充）
    それ以外の VALUE_SLOTS → 攻略・保存ネタ（セール時は先頭枠だけ優先）
    """
    chitchat_slots = tuple(getattr(config, "CHITCHAT_SLOTS", ()) or ())
    if slot in config.STRUGGLE_SLOTS:
        k = _struggle_position(slot)
        idx = (on.toordinal() * len(config.STRUGGLE_SLOTS) + k) % len(_STRUGGLE_POOL)
        return _STRUGGLE_POOL[idx]
    if slot in chitchat_slots:
        return _pick_chitchat(on, slot)

    label = active_sale_label(on)
    priority: ValuePost | None = None
    if label and "マラソン" in label:
        priority = _find("marathon-basics")
    elif label and "スーパーセール" in label:
        priority = _find("regret-checklist")

    tip_slots = tuple(s for s in config.VALUE_SLOTS if s not in _non_tip_slots())
    k = _static_position(slot)
    if priority is not None and k == 0:
        return priority

    idx = (on.toordinal() * max(1, len(tip_slots)) + k) % len(_POOL)
    picked = _POOL[idx]
    if priority is not None and picked.value_id == priority.value_id:
        picked = _POOL[(idx + 1) % len(_POOL)]
    return picked


def _find(value_id: str) -> ValuePost:
    for p in _POOL:
        if p.value_id == value_id:
            return p
    for p in _STRUGGLE_POOL:
        if p.value_id == value_id:
            return p
    for p in chitchat_pool():
        if p.value_id == value_id:
            return p
    raise KeyError(value_id)
