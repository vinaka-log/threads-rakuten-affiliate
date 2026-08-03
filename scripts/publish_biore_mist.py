"""One-shot: publish Biore cold handy mist Threads post."""

from __future__ import annotations

import asyncio
import os
import sys

from threads_client import ThreadsClient

MAIN = """暑がりの僕の夏の必須アイテム！
これないと夏は乗り切れる気がしない。

おすすめの使い方は、このスプレーを首後ろと両腕にプッシュした後に、ハンディファンで冷やすと、びっくりするくらい冷感が押し寄せてくるのでおすすめ！！
騙されたと思って試してみて欲しい👍

ビオレ 冷ハンディミスト
リフレッシュサボンの香り 120ml

気になる人はリプへ👇"""

REPLY = """▼商品はこちら
https://hb.afl.rakuten.co.jp/hgc/g00qvyfn.x8u2b9d8.g00qvyfn.x8u2cc06/?pc=https%3A%2F%2Fitem.rakuten.co.jp%2Fsundrug%2F4901301413123%2F&m=http%3A%2F%2Fm.rakuten.co.jp%2Fsundrug%2Fi%2F10105761%2F

※PR（アフィリエイトリンク）"""


async def main() -> int:
    texts = [MAIN.strip(), REPLY.strip()]
    print("=== MAIN ===")
    print(texts[0])
    print("=== REPLY ===")
    print(texts[1])
    client = ThreadsClient(
        access_token=os.environ["THREADS_ACCESS_TOKEN"],
        user_id=os.environ["THREADS_USER_ID"],
    )
    result = await client.publish_thread(texts, dry_run=False)
    print(f"post_ids={result.post_ids}")
    print(f"partial={result.partial}")
    print(f"warnings={result.warnings}")
    if not result.post_ids:
        print("publish failed: no post_ids", file=sys.stderr)
        return 1
    if result.partial:
        print("partial publish: reply failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
