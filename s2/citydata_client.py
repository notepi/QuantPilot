"""S2-local tushare client.

This module provides tushare API access for S2 module.
It reuses the unified tushare_proxy from wb module.
"""

from __future__ import annotations

# 确保 .env 文件被加载（优先级高于系统环境变量）
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

from wb.tushare_proxy import pro_api as _pro_api


def pro_api(token: str | None = None):
    """
    返回 tushare pro_api 对象。

    S2 模块统一使用 wb.tushare_proxy 接口，
    确保数据源配置一致性。

    Args:
        token: 可选的 tushare token，未提供时从 .env 读取

    Returns:
        tushare pro_api 对象
    """
    return _pro_api(token)


# 保持向后兼容的类名（旧代码可能直接实例化此类）
class S2CityDataAPI:
    """
    已弃用：请直接使用 pro_api() 函数。
    保留此类仅为向后兼容。
    """

    def __init__(self, token: str | None = None):
        self._pro = pro_api(token)

    def fund_daily(self, **kwargs):
        return self._pro.fund_daily(**kwargs)

    def __getattr__(self, name):
        return getattr(self._pro, name)
