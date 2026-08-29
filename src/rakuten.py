"""楽天市場 API クライアント（ランキング / 商品検索）。

新エンドポイント（openapi.rakuten.co.jp）では
applicationId（UUID）+ accessKey の両方が必須。
affiliateId を付けると affiliateUrl が返る。
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

import config


@dataclass(frozen=True)
class RakutenItem:
    item_code: str
    item_name: str
    item_price: int
    affiliate_url: str
    item_url: str
    review_average: float
    review_count: int
    shop_name: str
    genre_id: str
    rank: Optional[int] = None
    image_url: str = ""
    point_rate: int = 0
    # 応答 postageFlag: 0=送料込 / 1=送料別（Ichiba Item Search 2026-07-01）
    postage_flag: int = 0
    shop_of_the_year_flag: int = 0

    @property
    def short_name(self) -> str:
        """投稿向けに商品名を短縮（先頭装飾を除去 / 最大40字）。"""
        name = self.item_name.strip()
        # 先頭の【...】[…]（…）＼...／ を繰り返し除去
        prev = None
        while prev != name:
            prev = name
            name = re.sub(
                r"^(【[^】]*】|\[[^\]]*\]|（[^）]*）|\([^)]*\)|＼[^／]*／|\\[^/]*/)\s*",
                "",
                name,
            )
        # 末尾の「※...」注記を除去
        name = re.sub(r"※[^※]*$", "", name).strip()
        # 先頭の「〜★」宣伝セグメント（例: ポイント最大19倍★）を繰り返し除去
        while True:
            m = re.match(r"^[^★]{1,45}★\s*", name)
            if not m or len(name) - m.end() < 8:
                break
            name = name[m.end() :]
            # セグメント除去で先頭に現れた括弧装飾も再除去
            name = re.sub(r"^(【[^】]*】|\[[^\]]*\]|（[^）]*）|\([^)]*\))\s*", "", name)
        # 残った途中の装飾の前まで（十分長い場合のみ）
        for sep in ("【", "［", "[", "／", "/"):
            if sep in name:
                head = name.split(sep, 1)[0].strip()
                if len(head) >= 8:
                    name = head
                    break
        name = name.strip(" 　-–—|｜")
        # 削りすぎて商品名として意味をなさない場合は、注記だけ除いた元名にフォールバック
        if len(name) < 10:
            name = re.sub(r"※[^※]*$", "", self.item_name).strip()
        if len(name) > 40:
            name = name[:39] + "…"
        return name or self.item_name[:40]


class RakutenApiError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class RakutenClient:
    def __init__(
        self,
        application_id: Optional[str] = None,
        access_key: Optional[str] = None,
        affiliate_id: Optional[str] = None,
        *,
        timeout_sec: float = 30.0,
    ) -> None:
        self.application_id = (application_id or os.environ.get("RAKUTEN_APPLICATION_ID") or "").strip()
        self.access_key = (access_key or os.environ.get("RAKUTEN_ACCESS_KEY") or "").strip()
        self.affiliate_id = (affiliate_id or os.environ.get("RAKUTEN_AFFILIATE_ID") or "").strip()
        if not self.application_id:
            raise ValueError("RAKUTEN_APPLICATION_ID が未設定です")
        if not self.access_key:
            raise ValueError("RAKUTEN_ACCESS_KEY が未設定です")
        if not self.affiliate_id:
            raise ValueError("RAKUTEN_AFFILIATE_ID が未設定です")
        self.timeout_sec = timeout_sec
        # 楽天のアプリ登録で許可した Allowed websites と一致させる必要がある
        self.referer = (
            os.environ.get("RAKUTEN_REFERER") or "https://www.nisa-simulation.com/"
        ).strip()

    def _headers(self) -> Dict[str, str]:
        origin = self.referer.rstrip("/")
        return {"Referer": self.referer, "Origin": origin}

    def _base_params(self) -> Dict[str, str]:
        return {
            "applicationId": self.application_id,
            "accessKey": self.access_key,
            "affiliateId": self.affiliate_id,
            "format": "json",
        }

    def _get(self, url: str, params: Dict[str, Any], *, retries: int = 3) -> dict:
        last_err: Optional[Exception] = None
        with httpx.Client(timeout=self.timeout_sec, headers=self._headers()) as client:
            for attempt in range(retries):
                response = client.get(url, params=params)
                try:
                    data = response.json() if response.content else {}
                except Exception:
                    data = {"raw": response.text}
                if response.status_code == 429:
                    last_err = RakutenApiError(
                        f"楽天API失敗 429: {data}",
                        status_code=429,
                        payload=data,
                    )
                    # 短く待ってリトライ（連続検索でのレート制限対策）
                    time.sleep(1.2 * (attempt + 1))
                    continue
                if response.status_code >= 400:
                    raise RakutenApiError(
                        f"楽天API失敗 {response.status_code}: {data}",
                        status_code=response.status_code,
                        payload=data,
                    )
                if isinstance(data, dict) and data.get("error"):
                    raise RakutenApiError(
                        f"楽天APIエラー: {data.get('error_description') or data.get('error')}",
                        status_code=response.status_code,
                        payload=data,
                    )
                if not isinstance(data, dict):
                    raise RakutenApiError("楽天APIの応答が不正です", payload=data)
                return data
        assert last_err is not None
        raise last_err

    @staticmethod
    def _first_image_url(item: dict) -> str:
        """mediumImageUrls から投稿向けURLを1つ取る。可能なら解像度を上げる。"""
        for key in ("mediumImageUrls", "smallImageUrls"):
            arr = item.get(key) or []
            if not isinstance(arr, list) or not arr:
                continue
            first = arr[0]
            if isinstance(first, dict):
                url = str(first.get("imageUrl") or "").strip()
            else:
                url = str(first or "").strip()
            if not url:
                continue
            # 128x128 / 64x64 を大きめに（Threads掲載向け）
            url = re.sub(r"/128x128\.", "/400x400.", url)
            url = re.sub(r"/64x64\.", "/400x400.", url)
            url = re.sub(r"_ex=128x128", "_ex=400x400", url)
            return url
        return ""

    @staticmethod
    def _parse_item(raw: dict, *, rank: Optional[int] = None) -> Optional[RakutenItem]:
        item = raw.get("Item") if "Item" in raw else raw
        if not isinstance(item, dict):
            return None
        item_code = str(item.get("itemCode") or "").strip()
        affiliate_url = str(item.get("affiliateUrl") or "").strip()
        item_url = str(item.get("itemUrl") or "").strip()
        item_name = str(item.get("itemName") or "").strip()
        if not item_code or not item_name:
            return None
        if not affiliate_url:
            affiliate_url = item_url
        if not affiliate_url:
            return None
        try:
            price = int(item.get("itemPrice") or 0)
        except (TypeError, ValueError):
            price = 0
        try:
            review_average = float(item.get("reviewAverage") or 0)
        except (TypeError, ValueError):
            review_average = 0.0
        try:
            review_count = int(item.get("reviewCount") or 0)
        except (TypeError, ValueError):
            review_count = 0
        try:
            point_rate = int(float(item.get("pointRate") or 0))
        except (TypeError, ValueError):
            point_rate = 0
        try:
            postage_flag = int(item.get("postageFlag") or 0)
        except (TypeError, ValueError):
            postage_flag = 0
        try:
            soy = int(item.get("shopOfTheYearFlag") or 0)
        except (TypeError, ValueError):
            soy = 0
        rank_val = rank
        if rank_val is None and str(item.get("rank") or "").isdigit():
            rank_val = int(item["rank"])
        return RakutenItem(
            item_code=item_code,
            item_name=item_name,
            item_price=price,
            affiliate_url=affiliate_url,
            item_url=item_url,
            review_average=review_average,
            review_count=review_count,
            shop_name=str(item.get("shopName") or "").strip(),
            genre_id=str(item.get("genreId") or "").strip(),
            rank=rank_val,
            image_url=RakutenClient._first_image_url(item),
            point_rate=point_rate,
            postage_flag=postage_flag,
            shop_of_the_year_flag=soy,
        )

    def fetch_ranking(
        self,
        genre_id: str = "0",
        *,
        hits: int = config.RANKING_HITS,
    ) -> List[RakutenItem]:
        """ジャンル別売れ筋ランキングを取得。"""
        params = self._base_params()
        params["genreId"] = genre_id
        data = self._get(config.RAKUTEN_RANKING_URL, params)
        items_raw = data.get("Items") or []
        result: List[RakutenItem] = []
        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            # API応答は順位順とは限らないので、item自身の rank を使う
            parsed = self._parse_item(raw)
            if parsed:
                result.append(parsed)
        result.sort(key=lambda i: i.rank if i.rank is not None else 999)
        return result[:hits]

    @staticmethod
    def parse_item_url(url: str) -> Optional[tuple[str, str]]:
        """楽天商品URLから (shopCode, urlItemCode) を取り出す。"""
        raw = (url or "").strip()
        if not raw:
            return None
        # クエリ・フラグメントを落としてパスだけ見る
        raw = raw.split("#", 1)[0].split("?", 1)[0]
        m = re.search(r"item\.rakuten\.co\.jp/([^/]+)/([^/]+)/?", raw)
        if not m:
            return None
        shop, code = m.group(1).strip(), m.group(2).strip()
        if not shop or not code:
            return None
        return shop, code

    def deep_affiliate_url(self, item_url: str) -> str:
        """ディープリンク形式のアフィリエイトURLを組み立てる。

        APIの itemCode 解決に失敗したとき用。楽天アフィリエイトの
        `https://hb.afl.rakuten.co.jp/{affiliateId}/?pc=...&m=...` 形式。
        """
        clean = (item_url or "").strip().split("#", 1)[0].split("?", 1)[0]
        if clean and not clean.endswith("/"):
            clean += "/"
        from urllib.parse import quote

        enc = quote(clean, safe="")
        return f"https://hb.afl.rakuten.co.jp/{self.affiliate_id}/?pc={enc}&m={enc}"

    def fetch_item_by_code(self, item_code: str) -> Optional[RakutenItem]:
        """itemCode（shop:code）で1件取得。見つからなければ None。

        一部アプリ設定では itemCode パラメータ自体が 400 になるため、
        その場合は None を返す（呼び出し側でフォールバックする）。
        """
        code = (item_code or "").strip()
        if not code:
            return None
        params: Dict[str, Any] = self._base_params()
        params.update({"itemCode": code, "hits": 1})
        try:
            data = self._get(config.RAKUTEN_SEARCH_URL, params)
        except RakutenApiError as exc:
            # wrong_parameter / API Configuration not found 等は未対応扱い
            if exc.status_code == 400:
                return None
            raise
        items_raw = data.get("Items") or []
        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            parsed = self._parse_item(raw)
            if parsed:
                return parsed
        return None

    def fetch_item_by_url(self, item_url: str) -> Optional[RakutenItem]:
        """商品ページURLからアフィ付き商品情報を解決する。

        1) URLパスを itemCode (shop:code) として直接検索（対応環境のみ）
        2) shopCode + keyword=code で検索し、itemUrl が一致するものを採用
        """
        parsed_url = self.parse_item_url(item_url)
        if not parsed_url:
            return None
        shop, code = parsed_url
        direct = self.fetch_item_by_code(f"{shop}:{code}")
        if direct:
            return direct

        # URLの商品コードと API itemCode が一致しない店舗向けフォールバック
        params: Dict[str, Any] = self._base_params()
        params.update(
            {
                "shopCode": shop,
                "keyword": code,
                "hits": 30,
            }
        )
        try:
            data = self._get(config.RAKUTEN_SEARCH_URL, params)
        except RakutenApiError as exc:
            if exc.status_code == 400:
                # shopCode 未対応などの場合は keyword のみで再試行
                params = self._base_params()
                params.update({"keyword": f"{shop} {code}", "hits": 30})
                try:
                    data = self._get(config.RAKUTEN_SEARCH_URL, params)
                except RakutenApiError as exc2:
                    if exc2.status_code == 400:
                        return None
                    raise
            else:
                raise
        items_raw = data.get("Items") or []
        needle = f"/{shop}/{code}/"
        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            parsed = self._parse_item(raw)
            if not parsed:
                continue
            # affiliateUrl / itemUrl どちらにも元URLパスが含まれることが多い
            hay = f"{parsed.item_url} {parsed.affiliate_url}"
            if needle in hay or f"/{shop}/{code}" in hay:
                return parsed
        # キーワード一致が1件だけならそれを採用
        candidates = []
        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            parsed = self._parse_item(raw)
            if parsed:
                candidates.append(parsed)
        if len(candidates) == 1:
            return candidates[0]
        return None

    def search_items(
        self,
        keyword: str,
        *,
        hits: int = 10,
        sort: str = "-reviewCount",
        genre_id: Optional[str] = None,
        max_price: Optional[int] = None,
        pages: int = 3,
        postage_flag: Optional[int] = None,
    ) -> List[RakutenItem]:
        """キーワードで商品検索（悩み起点の選定用）。

        価格上限・複数ページを取り、クライアント側でもレビュー件数順に並べる。
        （APIの -reviewCount が薄い新規SKUを返すことがあるため）

        postage_flag:
          リクエスト側。1=送料込/送料無料のみ。None=指定なし（全件）。
        """
        per_page = min(max(hits, 1), 30)
        page_count = min(max(pages, 1), 5)
        seen: set[str] = set()
        result: List[RakutenItem] = []
        for page in range(1, page_count + 1):
            params: Dict[str, Any] = self._base_params()
            params.update(
                {
                    "keyword": keyword,
                    "hits": per_page,
                    "page": page,
                    "sort": sort,
                }
            )
            if genre_id:
                params["genreId"] = genre_id
            if max_price is not None and max_price > 0:
                params["maxPrice"] = int(max_price)
                params["minPrice"] = 1
            if postage_flag is not None:
                params["postageFlag"] = int(postage_flag)
            data = self._get(config.RAKUTEN_SEARCH_URL, params)
            items_raw = data.get("Items") or []
            if not items_raw:
                break
            for raw in items_raw:
                if not isinstance(raw, dict):
                    continue
                parsed = self._parse_item(raw)
                if not parsed or parsed.item_code in seen:
                    continue
                seen.add(parsed.item_code)
                result.append(parsed)
        result.sort(
            key=lambda i: (i.review_count, i.review_average, -i.item_price),
            reverse=True,
        )
        return result
