# Threads × 楽天アフィリエイト 自動投稿

楽天市場の売れ筋ランキングから商品を自動取得し、テンプレートで投稿文を生成して Threads に自動投稿する**自分専用**ツールです。

**ペルソナ A（固定）**: 共働き〜子育て世帯の「家庭の消耗品・時短買い」担当向け。  
日用品 / キッチンに絞り、悩みキーワード（洗剤切れ・水が重い等）で商品を選ぶ。美容・ファッション・ガジェット総合は扱わない。

- スケジュール: **毎日10投稿 JST**（共感5 : 雑談2 : 商品紹介2 : 攻略1）
  - **共働きリアル苦悩 5本**: 生活実感・あるある吐露
  - **どうでもいい雑談 2本**: テーマ無関係（中の人が人間に見えるためのブレ）
  - 商品紹介 2本: 夕方以降のみ。本投稿リンクなし + 自分リプ（冒頭 `#PR` + アフィリエイトURL）
  - 攻略・保存ネタ 1本: 18:00
  - ランキングダイジェストは一旦停止
  - 17:00 は再利用キュー優先
- 重複防止: `data/posted.json`（直近30日は同一 `itemCode` を再投稿しない）
- rank帯ローテ: 偶数日=1〜10位 / 奇数日=11〜30位（競合アカウントとの商品被りを回避）
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

- 景品表示法（ステマ規制）により、アフィリエイトを含む投稿には **広告であることの明示** が必要です。本ツールはリンクリプの先頭に `#PR` を自動挿入します。
- アフィリエイトURLは **本投稿ではなく自分リプ** に置きます。
- 楽天アフィリエイトで Threads を使う場合、**媒体登録**にアカウントURLを登録してください。
- 誇大表現・薬機法に触れる文言はテンプレートに入れていません。テンプレ改変時は注意してください。

## One-time setup

### 1. Threads アカウント

運用アカウント: [@kaimono_kuma](https://www.threads.com/@kaimono_kuma)（みつきリタイアとは別の専用アカウント）

| 項目 | 設定 |
|------|------|
| 表示名 | かいものくま｜日用品の買い時メモ |
| ユーザーネーム | `kaimono_kuma` |
| キャラクター | ほんわかシロクマ（ハート系絵文字は使わない） |
| ペルソナ | 共働き〜子育て世帯の買い足し担当（ペルソナ A） |
| 公開設定 | 公開（鍵アカ禁止・楽天規約） |

**表示名の考え方（競合調査）**

伸びている競合はだいたい `名前｜便益 or 専門領域` の型。

| アカウント例 | 表示名の型 |
|---|---|
| つむふたママ | 名前｜専門性（お得オタクの保育士） |
| おとママ | 名前｜誰向け×ラク（0〜3歳の育児ハック） |
| ねむこ | 名前┊願望×実績（楽したいママの買ってよかった） |
| りん | 名前｜変化（ROOMで暮らしを変えた人） |

→ くまはママ名乗らず差別化し、検索語になる **日用品** と行動喚起の **買い時メモ** を入れる。  
「チェック係」「売れ筋」だけだと、誰の何の役に立つかが弱い。

**自己紹介（そのまま貼付・150字以内）**

```
╲また切れた…を減らしたい共働きへ╱
日用品とキッチンの買い時を毎日メモ
・売れ筋ランキングの定点観測
・重いもの・ストック補充の候補
・ポイント日・セールの目安
PR・アフィリエイトリンクを含みます
```

プロフィール構成の型（競合共通）:  
①1行目で誰向けの痛み → ②何をする人か → ③発信の柱を箇条書き2〜3本 → ④PR表記。  
やらないこと: 美容・ファッション・ガジェット総合・なんでも売れ筋・ハート絵文字の多用。  
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
4. 以降は毎日3回のスケジュールに任せる

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
PYTHONPATH=src:. python src/post.py --dry-run --genre 100939

# 価値投稿（slot 0 / 2 / 4 / 8 は自動で価値投稿になる。楽天 env 不要）
PYTHONPATH=src:. python src/post.py --dry-run --slot 0
PYTHONPATH=src:. python src/post.py --dry-run --value --value-id marathon-basics

# 再利用枠（slot 4=17:00）。期限到来の候補があれば優先
PYTHONPATH=src:. python src/post.py --dry-run --slot 4
PYTHONPATH=src:. python src/post.py --list-reuse
PYTHONPATH=src:. python src/post.py --mark-reuse stock-buy

# ランキングダイジェスト（slot 3/5/6/9。楽天 env 必要）
PYTHONPATH=src:. python src/post.py --dry-run --slot 3
PYTHONPATH=src:. python src/post.py --dry-run --digest --digest-format quiz

# 本番投稿（要 Threads env）
export THREADS_ACCESS_TOKEN=...
export THREADS_USER_ID=...
PYTHONPATH=src:. python src/post.py --publish --slot 0
```

## 日内枠

| slot | 時刻(JST) | 内容 |
|------|-----------|------|
| 0 | 07:00 | **共働きリアル苦悩** |
| 1 | 08:00 | **どうでもいい雑談** |
| 2 | 12:00 | **共働きリアル苦悩** |
| 3 | 15:00 | **どうでもいい雑談** |
| 4 | 17:00 | **共働きリアル苦悩**（再利用優先） |
| 5 | 18:00 | 価値投稿（攻略・保存ネタ） |
| 6 | 19:00 | **商品紹介**（悩み×rank帯ローテ） |
| 7 | 20:00 | **商品紹介**（悩み×rank帯ローテ） |
| 8 | 21:00 | **共働きリアル苦悩** |
| 9 | 22:00 | **共働きリアル苦悩** |

枠の種別は `config.py` の `ITEM_SLOTS` / `DIGEST_SLOTS` / `VALUE_SLOTS` / `STRUGGLE_SLOTS` / `CHITCHAT_SLOTS` で変更できます。CLI では `--item` / `--value` / `--digest` で種別を強制、`--value-id` や `--digest-format`（top3 / quiz / sleeper）で内容を指定できます。

ジャンルは `config.py` の `GENRES` を日付×slot でローテします。ペルソナ A の主戦場:

- 日用品 (`100939`)
- キッチン (`551167`)

商品紹介はさらに `PAIN_INTENTS`（洗剤切れ・水が重い等）で悩みキーワード検索して選びます。水などは悩み側でジャンル `100227` を個別指定。

※ 総合ランキングは美容・ガジェットが混ざるため使わない。

品質フィルタ（`config.py`）:

- レビュー平均 `>= 4.3`
- レビュー件数 `>= 100`
- 価格 `> 0` かつ **`<= ¥3,000`**（`MAX_ITEM_PRICE`）
- 直近30日に投稿済みの `itemCode` は除外
- **悩み一致は必須**: 商品名が `PAIN_INTENTS.name_hints` にヒットしないものは載せない（洗剤コピーに美容液が乗る事故を防ぐ）
- 美容・ガジェット等は `BLOCK_NAME_HINTS` で除外

## 投稿フォーマット

### 商品紹介（slot 6 / 7）

1. **本投稿** … URLなし（商品画像添付）。構成は **悩み → 困り事 → 買うとこう助かる → 商品** →「リプ見て👇」
2. **自分リプ** … 1行目 `#PR` → 悩み/困り事/ベネフィット → 価格・レビュー → （ポイント倍率気配・5と0の日・セール）→ `affiliateUrl`

選定は `PAIN_INTENTS` の悩みキーワード検索が先。各悩みに `problem`（困り）と `benefit`（助かること）を持たせ、スペックより役立ちを先に伝える。  
既定テンプレは `hook-benefit`（他に `hook-stock` / `hook-heavy` / `hook-tonight` / `hook-reason`）。

### ランキングダイジェスト

現状は枠を停止中（`DIGEST_SLOTS` 空）。再開する場合は `config.py` で枠を戻す。形式は `top3` / `quiz` / `sleeper`。

### 価値投稿（slot 0 / 1 / 2 / 3 / 4 / 5 / 8 / 9）

リンク・PRなしの単発投稿。

- **slot 0 / 2 / 4 / 8 / 9（5本）**: **共働きリアル苦悩**。夜ご飯・寄り道・消耗品など生活実感の吐露
- **slot 1 / 3（2本）**: **どうでもいい雑談**。日用品と無関係。**一度出したら二度と使わない**。未使用が減ったら `chitchat_gen` が自動で草稿を `data/chitchat_pool.json` に追加（パーツ組み合わせ。`OPENAI_API_KEY` があれば LLM 生成を優先）
- **slot 5（18:00）**: セール攻略・レビューの読み方など保存ネタ

### 再利用（slot 4 = 17:00 優先）

参考運用の「伸びた投稿を3日に1回再利用」に対応。`data/reuse.json` のキューから、前回投稿から3日以上経過した価値投稿を優先投下します。

- 通常の価値投稿は自動でキュー登録
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
