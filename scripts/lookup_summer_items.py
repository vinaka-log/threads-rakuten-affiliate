"""Find summer cooling SKUs similar to the Biore mist hit post."""

from __future__ import annotations

from rakuten import RakutenClient


QUERIES = [
    ("biore-mint", "ビオレ 冷ハンディミスト ミント", ["冷ハンディミスト", "ビオレ"]),
    ("biore-soap", "ビオレ 冷ハンディミスト リフレッシュサボン", ["冷ハンディミスト", "サボン"]),
    ("gatsby-ice", "ギャツビー アイスデオドラント スプレー", ["ギャツビー", "アイス"]),
    ("cooling-sheet", "冷却シート 首 大人", ["冷却シート"]),
    ("cold-towel", "冷感タオル スポーツ", ["冷感タオル", "クールタオル"]),
    ("skin-vape", "スキンベープミスト イカリジン", ["スキンベープ", "ミスト"]),
]


def score(it, must_any: list[str]) -> float:
    n = it.item_name
    if not any(m in n for m in must_any):
        return -1
    s = 0.0
    if it.postage_flag == 0:
        s += 8
    if it.item_price <= 1500:
        s += 10
    elif it.item_price <= 2500:
        s += 5
    s += min(it.review_count, 3000) / 80.0
    s += it.review_average * 2
    if "詰め合わせ" in n or "セット" in n and it.item_price > 2000:
        s -= 5
    return s


def main() -> None:
    client = RakutenClient()
    for key, q, must in QUERIES:
        print("=" * 72)
        print(f"QUERY {key}: {q}")
        items = client.search_items(q, hits=30, pages=2, sort="-reviewCount", postage_flag=1)
        if not items:
            items = client.search_items(q, hits=30, pages=2, sort="-reviewCount")
        ranked = sorted(items, key=lambda it: score(it, must), reverse=True)
        ranked = [it for it in ranked if score(it, must) >= 0][:4]
        for i, it in enumerate(ranked, 1):
            url = it.affiliate_url or it.item_url
            mid = max(1, len(url) // 2)
            print(f"#{i} code={it.item_code}")
            print(f"name={it.item_name}")
            print(f"price={it.item_price} review={it.review_average}({it.review_count}) postage={it.postage_flag}")
            print(f"shop={it.shop_name}")
            print(f"url1={url[:mid]}")
            print(f"url2={url[mid:]}")
            print()


if __name__ == "__main__":
    main()
