"""
数据获取统一入口

支持两种模式：
1. 本地模式（use_local=True）：从本地CSV读取数据
2. 接口模式（use_local=False）：从接口抓取数据

所有数据通过 citydata 代理获取
"""
import os
from pathlib import Path
from typing import Optional
import pandas as pd
from dotenv import load_dotenv

# 导入 citydata 代理
try:
    from wb.tushare_proxy import pro_api as citydata_pro_api
except ImportError:
    citydata_pro_api = None

load_dotenv()

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "data" / "raw"


class DataFetcher:
    """数据获取统一入口（全部使用 citydata 代理）"""

    def __init__(
        self,
        use_local: bool = False,
    ):
        """
        初始化数据获取器

        Args:
            use_local: 是否使用本地数据
        """
        self.use_local = use_local

        # citydata 代理 API（用于所有数据）
        if citydata_pro_api and not use_local:
            self.pro = citydata_pro_api()
        else:
            self.pro = None

    # ==================== 本地数据读取 ====================

    def _load_csv(self, filename: str) -> Optional[pd.DataFrame]:
        """从本地CSV读取数据"""
        filepath = DATA_DIR / filename
        if not filepath.exists():
            return None
        df = pd.read_csv(filepath)
        # 确保 trade_date 为字符串格式
        if "trade_date" in df.columns:
            df["trade_date"] = df["trade_date"].astype(str)
        return df

    def get_fund_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """获取ETF日线行情"""
        if self.use_local:
            df = self._load_csv("fund_daily.csv")
            if df is None:
                return None
            # 过滤
            df = df[
                (df["ts_code"] == ts_code) &
                (df["trade_date"] >= start_date) &
                (df["trade_date"] <= end_date)
            ]
            return df.sort_values("trade_date") if len(df) > 0 else None

        # 接口模式
        if not self.pro:
            return None
        try:
            df = self.pro.fund_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
            return df if df is not None and len(df) > 0 else None
        except Exception as e:
            print(f"get_fund_daily error: {e}")
            return None

    def get_fund_share(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """获取ETF份额数据"""
        if self.use_local:
            df = self._load_csv("fund_share.csv")
            if df is None:
                return None
            df = df[
                (df["ts_code"] == ts_code) &
                (df["trade_date"] >= start_date) &
                (df["trade_date"] <= end_date)
            ]
            return df.sort_values("trade_date") if len(df) > 0 else None

        # 接口模式
        if not self.pro:
            return None
        try:
            df = self.pro.fund_share(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
            if df is None or len(df) == 0:
                return None
            df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
            return df if len(df) > 0 else None
        except Exception as e:
            print(f"get_fund_share error: {e}")
            return None

    def get_fund_portfolio(
        self,
        ts_code: str,
        start_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """获取ETF持仓成分股"""
        if self.use_local:
            df = self._load_csv("fund_portfolio.csv")
            if df is None:
                return None
            df = df[df["ts_code"] == ts_code]
            return df if len(df) > 0 else None

        # 接口模式
        if not self.pro:
            return None
        try:
            df = self.pro.fund_portfolio(
                ts_code=ts_code,
                start_date=start_date,
            )
            return df if df is not None and len(df) > 0 else None
        except Exception as e:
            print(f"get_fund_portfolio error: {e}")
            return None

    def get_daily_batch(
        self,
        ts_codes: list,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """批量获取A股日线行情"""
        if self.use_local:
            df = self._load_csv("daily.csv")
            if df is None:
                return None
            df = df[
                (df["ts_code"].isin(ts_codes)) &
                (df["trade_date"] >= start_date) &
                (df["trade_date"] <= end_date)
            ]
            return df.sort_values(["ts_code", "trade_date"]) if len(df) > 0 else None

        # 接口模式
        if not self.pro:
            return None
        try:
            codes_str = ",".join(ts_codes)
            df = self.pro.daily(
                ts_code=codes_str,
                start_date=start_date,
                end_date=end_date,
            )
            return df if df is not None and len(df) > 0 else None
        except Exception as e:
            print(f"get_daily_batch error: {e}")
            return None

    def get_hk_daily_batch(
        self,
        ts_codes: list,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """批量获取港股日线行情"""
        if self.use_local:
            df = self._load_csv("hk_daily.csv")
            if df is None:
                return None
            df = df[
                (df["ts_code"].isin(ts_codes)) &
                (df["trade_date"] >= start_date) &
                (df["trade_date"] <= end_date)
            ]
            return df.sort_values(["ts_code", "trade_date"]) if len(df) > 0 else None

        # 接口模式
        if not self.pro:
            return None
        try:
            codes_str = ",".join(ts_codes)
            df = self.pro.hk_daily(
                ts_code=codes_str,
                start_date=start_date,
                end_date=end_date,
            )
            return df if df is not None and len(df) > 0 else None
        except Exception as e:
            print(f"get_hk_daily_batch error: {e}")
            return None


# 单例实例
_data_fetcher: Optional[DataFetcher] = None


def get_data_fetcher(use_local: bool = False) -> DataFetcher:
    """获取数据获取器单例"""
    global _data_fetcher
    if _data_fetcher is None:
        _data_fetcher = DataFetcher(use_local=use_local)
    return _data_fetcher