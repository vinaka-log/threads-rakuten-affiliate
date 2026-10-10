"""Threads 長期アクセストークンを refresh する。

Meta 仕様:
  - 長期トークンは 60 日有効
  - 発行から 24 時間経過〜期限前なら refresh 可能
  - 期限切れ後は不可（再認可が必要）

使い方:
  THREADS_ACCESS_TOKEN=... python src/refresh_token.py
  → stdout に新しい access_token のみを出す（Secret 更新用）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Optional

import httpx

REFRESH_URL = "https://graph.threads.net/refresh_access_token"


class TokenRefreshError(RuntimeError):
    def __init__(self, message: str, *, payload: Optional[dict] = None):
        super().__init__(message)
        self.payload = payload or {}


def refresh_long_lived_token(
    access_token: str,
    *,
    client: Optional[httpx.Client] = None,
    timeout_sec: float = 30.0,
) -> dict[str, Any]:
    if not access_token:
        raise TokenRefreshError("THREADS_ACCESS_TOKEN が未設定です")

    params = {
        "grant_type": "th_refresh_token",
        "access_token": access_token,
    }
    own = client is None
    http = client or httpx.Client(timeout=timeout_sec)
    try:
        response = http.get(REFRESH_URL, params=params)
        data = response.json() if response.content else {}
        if not isinstance(data, dict):
            raise TokenRefreshError(
                f"予期しないレスポンス: {data!r}",
                payload={},
            )
        if response.status_code >= 400 or "access_token" not in data:
            err = data.get("error") if isinstance(data.get("error"), dict) else {}
            msg = err.get("message") or data
            raise TokenRefreshError(
                f"トークン refresh 失敗: {msg}",
                payload=data,
            )
        return data
    finally:
        if own:
            http.close()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh Threads long-lived access token")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON (access_token, expires_in, ...) instead of token only",
    )
    args = parser.parse_args(argv)

    token = (os.environ.get("THREADS_ACCESS_TOKEN") or "").strip()
    try:
        data = refresh_long_lived_token(token)
    except TokenRefreshError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print(
            "期限切れの場合は README「トークン更新」で再発行が必要です。"
            "発行から24時間未満だと refresh できない場合があります。",
            file=sys.stderr,
        )
        return 1

    if args.json:
        print(json.dumps(data, ensure_ascii=False))
    else:
        print(data["access_token"])
    expires_in = data.get("expires_in")
    if expires_in is not None:
        days = float(expires_in) / 86400.0
        print(f"expires_in={expires_in}sec (~{days:.1f} days)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
