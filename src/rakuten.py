"""楽天市場 API クライアント（ランキング / 商品検索）。

新エンドポイント（openapi.rakuten.co.jp）では
applicationId（UUID）+ accessKey の両方が必須。
affiliateId を付けると affiliateUrl が返る。
"""

from __future__ import annotations

import os
import re
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

    def _get(self, url: str, params: Dict[str, Any]) -> dict:
        with httpx.Client(timeout=self.timeout_sec, headers=self._headers()) as client:
            response = client.get(url, params=params)
            try:
                data = response.json() if response.content else {}
            except Exception:
                data = {"raw": response.text}
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

    def search_items(
        self,
        keyword: str,
        *,
        hits: int = 10,
        sort: str = "-reviewCount",
    ) -> List[RakutenItem]:
        """キーワードで商品検索（補助用）。"""
        params = self._base_params()
        params.update(
            {
                "keyword": keyword,
                "hits": min(max(hits, 1), 30),
                "sort": sort,
            }
        )
        data = self._get(config.RAKUTEN_SEARCH_URL, params)
        items_raw = data.get("Items") or []
        result: List[RakutenItem] = []
        for raw in items_raw:
            if not isinstance(raw, dict):
                continue
            parsed = self._parse_item(raw)
            if parsed:
                result.append(parsed)
        return result
