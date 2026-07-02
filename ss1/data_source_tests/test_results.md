# SS1 数据源验证结果

**测试时间**: 2026-06-25 23:18:16

## ETF日线

| 源 | 标的 | 可用 | 最新日期 | 历史深度 | 能喂给S1 |
|---|---|---|---|---|---|
| 腾讯 ETF K线 | 159567.SZ | yes | 20260625 | 260 | yes |
| citydata fund_daily | 159567.SZ | yes | 20260625 | 146 | yes |
| akshare fund_etf_hist_em | 159567.SZ | no |  | 0 | no |
| 腾讯 ETF K线 | 159557.SZ | yes | 20260625 | 260 | yes |
| citydata fund_daily | 159557.SZ | yes | 20260625 | 146 | yes |
| akshare fund_etf_hist_em | 159557.SZ | no |  | 0 | no |

## ETF份额

| 源 | 标的 | 可用 | 最新日期 | 历史深度 | 能喂给S1 |
|---|---|---|---|---|---|
| citydata fund_share | 159567.SZ | yes | 20260625 | 16 | yes |
| 东方财富 fund_etf_spot_em | 159567.SZ | yes | 20260625 | 1 | yes |

## 持仓/成分

| 源 | 标的 | 可用 | 最新日期 | 历史深度 | 能喂给S1 |
|---|---|---|---|---|---|
| 东方财富 ETF持仓 | 159567 | no |  | 0 | no |

## 持仓股票日线

| 源 | 标的 | 可用 | 最新日期 | 历史深度 | 能喂给S1 |
|---|---|---|---|---|---|
| 腾讯港股K线 | 09926.HK | yes | 20260625 | 260 | yes |
| akshare stock_hk_hist | 09926.HK | no |  | 0 | no |
| 腾讯港股K线 | 01801.HK | yes | 20260625 | 260 | yes |
| akshare stock_hk_hist | 01801.HK | no |  | 0 | no |
| 腾讯港股K线 | 01093.HK | yes | 20260625 | 260 | yes |
| akshare stock_hk_hist | 01093.HK | no |  | 0 | no |

## 失败详情

### akshare fund_etf_hist_em - 159567.SZ

**失败原因**: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))

### akshare fund_etf_hist_em - 159557.SZ

**失败原因**: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))

### 东方财富 ETF持仓 - 159567

**失败原因**: module 'akshare' has no attribute 'fund_etf_portfolio_em'

### akshare stock_hk_hist - 09926.HK

**失败原因**: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))

### akshare stock_hk_hist - 01801.HK

**失败原因**: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))

### akshare stock_hk_hist - 01093.HK

**失败原因**: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))

