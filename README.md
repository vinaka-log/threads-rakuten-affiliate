# Threads × 楽天アフィリエイト 自動投稿

楽天市場の売れ筋ランキングから商品を自動取得し、テンプレートで投稿文を生成して Threads に自動投稿する**自分専用**ツールです。

**ペルソナ B（固定）**: 妊娠中〜未就学（特に0〜2歳）の「ベビーグッズ買い足し」担当向け。  
お出かけ・ねんね・収納などに絞り、悩みキーワードで商品を選ぶ。日用品総合・美容・ファッション・ガジェットは扱わない。  
表示名: **かいものくま｜0〜2歳の買い足しメモ**

- スケジュール: **毎日10投稿 JST**（repo は public のため Actions 枠は消費しない）
  - **アンケート 3本（08:00 / 12:30 / 19:30）**: Threads標準の4択ポール。季節＋軽いトレンド。商品・PRなし
  - **雑談 3本（09:30 / 14:00 / 21:00）**: テーマ無関係の一度きり雑談
  - **ジブリ大喜利 2本（11:00 / 18:00）**: 公式場面写真＋買い足しあるある（URL・PRなし）
  - **商品紹介 2本（16:00 / 22:00）**: 本投稿は育児あるある＋問い（商品名・画像なし）。自分リプ1=うちの候補メモ、リプ2=URL＋`※PR`
  - ランキングダイジェストは停止
- 重複防止: `data/posted.json`（直近30日は同一 `itemCode` を再投稿しない）
- rank帯ローテ: 偶数日=1〜10位 / 奇数日=11〜30位（競合アカウントとの商品被りを回避）
- 送料: 送料込（postageFlag）を優先。送料別は候補が送料込だけのときは採用しない
- セール連動: 5と0のつく日は自動でポイントアップ告知をリプに追記。マラソン等は `config.SALE_PERIODS` に日程を追記

## 構成

```
.
├── .github/workflows/daily.yml
├── config.py                 # ジャンル・品質フィルタ・枠・セール日程
├── data/posted.json          # 投稿済み台帳
├── data/reuse.json           # 価値投稿の再利用キュー
├── requirements.txt
└── src/
    ├── threads_client.py     # Meta Threads Graph API
    ├── rakuten.py            # 楽天ランキング / 検索 API
    ├── picker.py             # ジャンルローテ + rank帯ローテ + 台帳
    ├── composer.py           # 投稿文テンプレート
    ├── value_posts.py        # 価値投稿（リンクなし）のプール
    ├── reuse.py              # 伸びた投稿の3日おき再利用
    ├── sale.py               # 5と0のつく日・セール期間判定
    └── post.py               # CLI
```

## 規約・法律上の前提

- 景品表示法（ステマ規制）により、アフィリエイトを含む投稿には **広告であることの明示** が必要です。本ツールは **最終リプの末尾** に `※PR` を自動挿入します（本投稿・メモリプには出さない）。
- アフィリエイトURLは **本投稿ではなく最終リプ** に置きます。
- 楽天アフィリエイトで Threads を使う場合、**媒体登録**にアカウントURLを登録してください。
- 誇大表現・薬機法に触れる文言はテンプレートに入れていません。テンプレ改変時は注意してください。

## One-time setup

### 1. Threads アカウント

運用アカウント: [@kaimono_kuma](https://www.threads.com/@kaimono_kuma)（みつきリタイアとは別の専用アカウント）

| 項目 | 設定 |
|------|------|
| 表示名 | かいものくま｜0〜2歳の買い足しメモ |
| ユーザーネーム | `kaimono_kuma` |
| キャラクター | ほんわかシロクマ（ハート系絵文字は使わない） |
| ペルソナ | 妊娠中〜0〜2歳のベビーグッズ買い足し担当（ペルソナ B） |
| 公開設定 | 公開（鍵アカ禁止・楽天規約） |

**表示名の考え方（競合調査）**

伸びている競合はだいたい `名前｜便益 or 専門領域` の型。

| アカウント例 | 表示名の型 |
|---|---|
| つむふたママ | 名前｜専門性（お得オタクの保育士） |
| おとママ | 名前｜誰向け×ラク（0〜3歳の育児ハック） |
| ねむこ | 名前┊願望×実績（楽したいママの買ってよかった） |
| りん | 名前｜変化（ROOMで暮らしを変えた人） |

→ くまはママ名乗らず差別化し、検索語になる **0〜2歳** と行動喚起の **買い足しメモ** を入れる。  
「チェック係」「売れ筋」だけだと、誰の何の役に立つかが弱い。

**自己紹介（そのまま貼付・150字以内）**

```
╲0〜2歳の買い足しを楽天に寄せたい人へ╱
ベビーグッズの買い時を毎日メモ
・お出かけ・ねんね・収納の候補
・売れ筋と口コミの定点観測
・ポイント日・セールの目安
PR・アフィリエイトリンクを含みます
```

プロフィール構成の型（競合共通）:  
①1行目で誰向けの痛み → ②何をする人か → ③発信の柱を箇条書き2〜3本 → ④PR表記。  
やらないこと: 日用品総合・美容・ファッション・ガジェット・なんでも売れ筋・ハート絵文字の多用。  
リンク欄は将来的に楽天ROOMを開設して一番上に置くのが定石。

### 2. Meta Threads API

1. [Meta Developer](https://developers.facebook.com/) でアプリ作成（または既存）
2. Threads 製品を追加し、権限に次を含める
   - `threads_basic`
   - `threads_content_publish`
   - `threads_manage_replies`（自分リプ連鎖に必須）
   - `threads_manage_insights`（任意・伸びた投稿の再利用優先度に使用）
3. 長期アクセストークンと Threads User ID を控える

### 3. 楽天ウェブサービス + アフィリエイト

1. [楽天 Developer Dashboard](https://webservice.rakuten.co.jp/app/list) でアプリ登録  
   - `applicationId` は **UUID形式**（旧・数字のみIDは新APIで使えません）  
   - `accessKey` も取得
2. [楽天アフィリエイト](https://affiliate.rakuten.co.jp/) でアフィリエイトIDを取得
3. 媒体に Threads アカウントURLを登録（審査完了を確認）

APIドキュメント:

- [Ichiba Item Ranking](https://webservice.rakuten.co.jp/documentation/ichiba-item-ranking)
- [Ichiba Item Search](https://webservice.rakuten.co.jp/documentation/ichiba-item-search)

### 4. GitHub Secrets

Repo → **Settings → Secrets and variables → Actions**:

| Secret | 内容 |
|--------|------|
| `THREADS_ACCESS_TOKEN` | Meta 長期トークン |
| `THREADS_USER_ID` | Threads ユーザ ID |
| `RAKUTEN_APPLICATION_ID` | 楽天 applicationId（UUID） |
| `RAKUTEN_ACCESS_KEY` | 楽天 accessKey |
| `RAKUTEN_AFFILIATE_ID` | 楽天アフィリエイトID |

### 5. 動作確認

1. Actions → **Threads Rakuten daily post** → **Run workflow**
2. まず `dry_run = true` で本文ログを確認
3. 問題なければ `dry_run = false` で1回投稿
4. 以降は毎日10回のスケジュールに任せる

## ローカル

```bash
cd /path/to/threads-rakuten-affiliate
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export RAKUTEN_APPLICATION_ID=...
export RAKUTEN_ACCESS_KEY=...
export RAKUTEN_AFFILIATE_ID=...

# 本文だけ（投稿しない）
PYTHONPATH=src:. python src/post.py --dry-run --slot 0
PYTHONPATH=src:. python src/post.py --list-genres
PYTHONPATH=src:. python src/post.py --dry-run --genre 100533

# アンケート / 雑談 / 大喜利（楽天 env 不要）
PYTHONPATH=src:. python src/post.py --dry-run --slot 0
PYTHONPATH=src:. python src/post.py --dry-run --slot 1
PYTHONPATH=src:. python src/post.py --dry-run --slot 2

# 商品紹介（slot 5 / 9。楽天 env 必要）
PYTHONPATH=src:. python src/post.py --dry-run --slot 5
PYTHONPATH=src:. python src/post.py --list-reuse
PYTHONPATH=src:. python src/post.py --mark-reuse stock-buy

# 本番投稿（要 Threads env）
export THREADS_ACCESS_TOKEN=...
export THREADS_USER_ID=...
PYTHONPATH=src:. python src/post.py --publish --slot 0
```

## 日内枠

| slot | 時刻(JST) | 内容 |
|------|-----------|------|
| 0 | 08:00 | **公式4択アンケート** |
| 1 | 09:30 | **雑談** |
| 2 | 11:00 | **ジブリ大喜利** |
| 3 | 12:30 | **公式4択アンケート** |
| 4 | 14:00 | **雑談** |
| 5 | 16:00 | **商品紹介** |
| 6 | 18:00 | **ジブリ大喜利** |
| 7 | 19:30 | **公式4択アンケート** |
| 8 | 21:00 | **雑談** |
| 9 | 22:00 | **商品紹介** |

枠の種別は `config.py` の `ITEM_SLOTS` / `OGIRI_SLOTS` / `TIMESAVE_ITEM_SLOTS` / `DIGEST_SLOTS` / `VALUE_SLOTS` / `STRUGGLE_SLOTS` / `CHITCHAT_SLOTS` / `ASK_CHITCHAT_SLOTS` で変更できます。CLI では `--item` / `--value` / `--ogiri` / `--digest` で種別を強制、`--value-id` や `--digest-format`（top3 / quiz / sleeper）で内容を指定できます。

ジャンルは `config.py` の `GENRES` を日付×slot でローテします。ペルソナ B の主戦場:

- キッズ・ベビー・マタニティ (`100533`)
- ベビーカー (`200833`)
- ベビー用寝具・ベッド (`200822`)

商品紹介はさらに `PAIN_INTENTS`（レインカバー・ねんね・おむつ収納等）で悩みキーワード検索して選びます。悩み側でサブジャンルや `max_price` を個別指定できます。

※ 総合ランキングや日用品総合は使わない。美容・ガジェット・大人向け消耗品は除外。

品質フィルタ（`config.py`）:

- レビュー平均 `>= 4.3`
- レビュー件数 `>= 80`
- 価格 `> 0` かつ **`<= ¥10,000`**（`MAX_ITEM_PRICE`。悩み単位で `max_price` 上書き可。例: ベビー枕は12000）
- **送料込を優先**（検索 `postageFlag=1` → 応答 `postageFlag=0`）。送料込が取れるときは送料別を選ばない
- 直近30日に投稿済みの `itemCode` は除外
- **悩み一致は必須**: 商品名が `PAIN_INTENTS.name_hints` にヒットしないものは載せない
- 美容・ガジェット等は `BLOCK_NAME_HINTS` で除外

## 投稿フォーマット

### 商品紹介（slot 5 / 9 = 16:00 / 22:00）

売り込み感を出さない。フィードは会話、欲しい人だけリンクを開ける。

1. **本投稿** … URLなし・商品名なし・商品画像なし（目安〜120字）。育児あるある → 短い共感 → 問い。価格・レビュー・PRなし
2. **自分リプ1** … `うちの候補はこれ。` + 商品名 + 注意点（必要なら今日のポイント日だけ）。リンク・PRなし
3. **自分リプ2** … URL + 末尾 `※PR` のみ

誤マッチは `exclude_name_hints` / `BLOCK_NAME_HINTS` で除外。

選定は `PAIN_INTENTS` の悩みキーワード検索が先。各悩みに `problem`（困り）と `benefit`（助かること）を持たせ、売り込みより「あるある→助かった」を先に伝える。  
テンプレは `hook-must` / `hook-scene` / `hook-tip` / `hook-honest` / `hook-heavy` を日付×商品でローテ（旧IDは自動で新IDへ寄せる）。

### ランキングダイジェスト

現状は枠を停止中（`DIGEST_SLOTS` 空）。再開する場合は `config.py` で枠を戻す。形式は `top3` / `quiz` / `sleeper`。

### 価値投稿（アンケート / 雑談 / 大喜利）

Threads API の `poll_attachment`（option_a〜d、各25字以内）を使ったネイティブ投票。

- **アンケート（08:00 / 12:30 / 19:30）**: 短い質問文 + 4択。`data/ask_chitchat_pool.json` から一度きり消費し、減ったら自動補充
- **雑談（09:30 / 14:00 / 21:00）**: テーマ無関係の一度きり雑談。`data/chitchat_pool.json`
- **ジブリ大喜利（11:00 / 18:00）**: 公式場面写真＋買い足しあるある。URL・PRなし
- 商品・PR・外部リンクなし（商品枠以外）。重い事件・政治ネタは除外
- 投票UIが使えない場合はテキスト投稿へフォールバック（警告ログ）

例:
```
夏といえばアイス、推しは？
[しろくまくん] [ガリガリ君] [ハーゲンダッツ] [その他]
```

### 再利用

アンケート枠では再利用しない（一度きり）。商品以外の価値投稿を手動で再利用したい場合は `python src/post.py --mark-reuse …` を使う。

- 伸びた投稿は手動で優先度アップ: `python src/post.py --mark-reuse stock-buy`
- Insights 権限がある場合: `python src/post.py --sync-insights` で views/likes を取り込み
- キュー確認: `python src/post.py --list-reuse`

### 共通ルール

- ハート系絵文字は使いません（🐻‍❄️は可）
- 全投稿を問いかけで締めて返信を促します

## 失敗時の切り分け

| 症状 | 原因 | 対処 |
|------|------|------|
| `Missing ... secrets` | Secrets 未設定 | GitHub Secrets を確認 |
| `RAKUTEN_* が未設定` | 環境変数不足 | export または Secrets |
| `accessKey must be present` | 旧APIキー | Developer Dashboard で再登録（UUID+accessKey） |
| `code: 10` / permission | リプ権限不足 | `threads_manage_replies` 追加→トークン再発行 |
| `投稿可能な商品がありません` | フィルタで全滅 | `DEDUP_DAYS` / レビュー閾値を一時緩和、またはジャンル追加 |

## ライセンス / 注意

個人利用前提です。楽天・Meta・景表法の規約変更に追随する責任は運用者にあります。投資助言ツールではありません。
