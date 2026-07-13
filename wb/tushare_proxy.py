"""
tushare_proxy.py - Tushare API 统一接口层

目标：业务代码零改动，统一使用 tushare 官方 SDK。

用法：
    from wb.tushare_proxy import pro_api
    pro = pro_api()

    # 调用接口：
    df = pro.daily(ts_code='688333.SH', start_date='20260310', end_date='20260317')
    df = pro.fund_daily(ts_code='589720.SH', start_date='20250801', end_date='20260714')
"""

import os

try:
    import tushare as ts
except ImportError:
    raise ImportError("请安装 tushare: pip install tushare")

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(dotenv_path: str = ".env") -> bool:
        """轻量兜底：在未安装 python-dotenv 时，按 KEY=VALUE 形式加载 .env。"""
        if not os.path.exists(dotenv_path):
            return False
        loaded = False
        with open(dotenv_path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
                loaded = True
        return loaded

load_dotenv(override=True)  # .env 优先级高于系统环境变量


def pro_api(token: str = None):
    """
    返回 tushare pro_api 对象。

    优先级：
    1. 显式传入的 token
    2. 环境变量 TUSHARE_TOKEN
    3. 环境变量 CITYDATA_TOKEN（向后兼容）

    用法：
        from wb.tushare_proxy import pro_api
        pro = pro_api()          # 从 .env 读 TUSHARE_TOKEN
        pro = pro_api("your_token")  # 显式传入
    """
    final_token = (
        token
        or os.getenv("TUSHARE_TOKEN")
        or os.getenv("CITYDATA_TOKEN")
    )
    if not final_token:
        raise ValueError(
            "未找到 token，请在 .env 中设置 TUSHARE_TOKEN"
        )

    return ts.pro_api(final_token)
