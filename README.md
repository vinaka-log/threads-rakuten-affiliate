# Threads × 楽天アフィリエイト 自動投稿

楽天市場の売れ筋ランキングから商品を自動取得し、テンプレートで投稿文を生成して Threads に自動投稿する**自分専用**ツールです。

- スケジュール: **毎日10投稿 JST**（価値提供8 : 商品紹介2 の比率）
  - 商品紹介 2本: 本投稿リンクなし + 自分リプ（冒頭 `#PR` + アフィリエイトURL）
  - ランキングダイジェスト 4本: リンクなし。毎日ランキングから自動生成されるので内容が被らない
  - 静的価値投稿 4本: リンクなしの保存ネタ36本（セール攻略・レビューの読み方等）を9日周期でローテ
- 重複防止: `data/posted.json`（直近30日は同一 `itemCode` を再投稿しない）
- rank帯ローテ: 偶数日=1〜10位 / 奇数日=11〜30位（競合アカウントとの商品被りを回避）
- セール連動: 5と0のつく日は自動でポイントアップ告知をリプに追記。マラソン等は `config.SALE_PERIODS` に日程を追記

## 構成

```
.
├── .github/workflows/daily.yml
├── config.py                 # ジャンル・品質フィルタ・枠・セール日程
├── data/posted.json          # 投稿済み台帳
├── requirements.txt
└── src/
    ├── threads_client.py     # Meta Threads Graph API
    ├── rakuten.py            # 楽天ランキング / 検索 API
    ├── picker.py             # ジャンルローテ + rank帯ローテ + 台帳
    ├── composer.py           # 投稿文テンプレート
    ├── value_posts.py        # 価値投稿（リンクなし）のプール
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
| 表示名 | かいものくま🐻‍❄️｜楽天の売れ筋チェック係 |
| ユーザーネーム | `kaimono_kuma` |
| キャラクター | ほんわかシロクマ（ハート系絵文字は使わない） |
| 公開設定 | 公開（鍵アカ禁止・楽天規約） |

**自己紹介（そのまま貼付）**

```
毎日楽天のランキングを見てるしろくまです🐻‍❄️
日用品/キッチン/食品/売れてるもの全般
「これ買って正解?」の答え合わせにどうぞ
PR・アフィリエイトリンクを含みます
```

プロフィール構成の型（競合調査より）: ①何の人か → ②ジャンルをスラッシュ区切り → ③読者メリット → ④PR表記。  
リンク欄は将来的に楽天ROOMを開設して一番上に置くのが定石。

### 2. Meta Threads API

1. [Meta Developer](https://developers.facebook.com/) でアプリ作成（または既存）
2. Threads 製品を追加し、権限に次を含める
   - `threads_basic`
   - `threads_content_publish`
   - `threads_manage_replies`（自分リプ連鎖に必須）
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

# 価値投稿（slot 0/3/5/8 は自動で価値投稿になる。楽天 env 不要）
PYTHONPATH=src:. python src/post.py --dry-run --slot 0
PYTHONPATH=src:. python src/post.py --dry-run --value --value-id marathon-basics

# ランキングダイジェスト（slot 2/4/6/9。楽天 env 必要）
PYTHONPATH=src:. python src/post.py --dry-run --slot 2
PYTHONPATH=src:. python src/post.py --dry-run --digest --digest-format quiz

# 本番投稿（要 Threads env）
export THREADS_ACCESS_TOKEN=...
export THREADS_USER_ID=...
PYTHONPATH=src:. python src/post.py --publish --slot 0
```

## 日内枠

| slot | 時刻(JST) | 内容 |
|------|-----------|------|
| 0 | 07:00 | 価値投稿（静的プール） |
| 1 | 08:00 | **商品紹介**（ジャンル×rank帯ローテ） |
| 2 | 09:30 | ランキングダイジェスト |
| 3 | 12:00 | 価値投稿（静的プール） |
| 4 | 15:00 | ランキングダイジェスト |
| 5 | 17:00 | 価値投稿（静的プール） |
| 6 | 18:30 | ランキングダイジェスト |
| 7 | 20:00 | **商品紹介**（ジャンル×rank帯ローテ） |
| 8 | 21:00 | 価値投稿（静的プール） |
| 9 | 22:30 | ランキングダイジェスト |

枠の種別は `config.py` の `ITEM_SLOTS` / `DIGEST_SLOTS` / `VALUE_SLOTS` で変更できます。CLI では `--item` / `--value` / `--digest` で種別を強制、`--value-id` や `--digest-format`（top3 / quiz / sleeper）で内容を指定できます。

ジャンルは `config.py` の `GENRES` を日付×slot でローテします。初期値:

- 総合 (`0`)
- 日用品 (`100939`)
- ドリンク (`100227`)
- キッチン (`551167`)

品質フィルタ（`config.py`）:

- レビュー平均 `>= 4.0`
- レビュー件数 `>= 100`
- 直近30日に投稿済みの `itemCode` は除外

## 投稿フォーマット

### 商品紹介（slot 1 / 7）

1. **本投稿** … URLなし。1行目は42字以内の悩み・あるあるフック（商品名から入らない）→ 商品 →「リプ見て👇」→ **問いかけで締める**
2. **自分リプ** … 1行目 `#PR` → 価格・レビュー → （5と0のつく日・セール中なら「今日買う理由」を自動追記）→ `affiliateUrl`

テンプレは `hook-honne` / `hook-minna` / `hook-teiten` / `hook-price` の4種を商品×日付で自動選択。すべて「毎日ランキングを見てるしろくま」の脱力・正直トーンで統一しています。

### ランキングダイジェスト（slot 2 / 4 / 6 / 9）

楽天ランキングから毎日自動生成するリンクなし投稿。内容が日々変わるため文面の重複が起きません。3形式をローテします。

- `top3` … 上位3件のメモ + ひとこと
- `quiz` … 2〜3位を見せて「1位は?」→ 答えを自分リプで公開（返信を誘発）
- `sleeper` … 上位のすぐ下の「じわじわ来てるゾーン」を紹介

### 価値投稿（slot 0 / 3 / 5 / 8）

リンク・PRなしの単発投稿。セール攻略、レビューの読み方、ポイント計算、雑談問いかけ、失敗談など「保存したくなるネタ」36本を `value_posts.py` のプールから日付ローテで選びます（9日で一巡・同日重複なし）。マラソン/スーパーセール期間中はその日の最初の枠で攻略系を優先します。

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
