"""S2-local citydata client.

This module intentionally lives under s2 so optional S2 observation refreshes do
not depend on or modify the S1 data adapter.
"""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(dotenv_path: str = ".env") -> bool:
        if not os.path.exists(dotenv_path):
            return False
        loaded = False
        with open(dotenv_path, encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
                loaded = True
        return loaded


load_dotenv()

PROXY_BASE_URL = "https://tushare.citydata.club"


def _frame_from_payload(payload: Any) -> pd.DataFrame:
    if not payload:
        return pd.DataFrame()
    if isinstance(payload, dict):
        nested = payload.get("data")
        if isinstance(nested, dict):
            fields = nested.get("fields")
            items = nested.get("items")
            if isinstance(items, list):
                if not items:
                    return pd.DataFrame()
                if isinstance(items[0], dict):
                    return pd.DataFrame(items)
                if isinstance(fields, list):
                    return pd.DataFrame(items, columns=fields)
        if isinstance(nested, list):
            if not nested:
                return pd.DataFrame()
            if len(nested) >= 2 and isinstance(nested[0], list) and isinstance(nested[1], list):
                rows = nested[1]
                if rows and isinstance(rows[0], dict):
                    return pd.DataFrame(rows)
                return pd.DataFrame(rows, columns=nested[0])
            if isinstance(nested[0], dict):
                return pd.DataFrame(nested)
        fields = payload.get("fields")
        items = payload.get("items")
        if isinstance(items, list):
            if not items:
                return pd.DataFrame()
            if isinstance(items[0], dict):
                return pd.DataFrame(items)
            if isinstance(fields, list):
                return pd.DataFrame(items, columns=fields)
    return pd.DataFrame(payload)


class S2CityDataAPI:
    def __init__(self, token: str | None = None, base_url: str = PROXY_BASE_URL):
        self._token = token or os.getenv("CITYDATA_TOKEN") or os.getenv("TUSHARE_TOKEN")
        if not self._token:
            raise ValueError("未找到 token，请在 .env 中设置 CITYDATA_TOKEN")
        self._base_url = base_url

    def _call(self, api_name: str, **kwargs: object) -> pd.DataFrame:
        params = {"TOKEN": self._token}
        params.update({key: value for key, value in kwargs.items() if value not in {None, ""}})
        last_error: Exception | None = None
        for _ in range(2):
            try:
                response = requests.post(f"{self._base_url}/{api_name}", data=params, timeout=30)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict) and payload.get("code") not in {None, 0, "0"} and payload.get("msg"):
                    raise PermissionError(str(payload.get("msg")))
                return _frame_from_payload(payload)
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as exc:
                last_error = exc
        if last_error:
            raise last_error
        return pd.DataFrame()

    def fund_daily(self, **kwargs: object) -> pd.DataFrame:
        return self._call("fund_daily", **kwargs)


def pro_api(token: str | None = None) -> S2CityDataAPI:
    return S2CityDataAPI(token=token)
