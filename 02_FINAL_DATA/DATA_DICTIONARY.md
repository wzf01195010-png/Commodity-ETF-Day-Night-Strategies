# Data and model inputs

provided_prices/*.csv：九只实际输入CSV；保留提供文件的全部字段、预热行及数值字节。Date为本地交易日期，in_sample选择固定4776日；GLD/SLV/USO的Prior_session_date/Prior_Close/Prior_Adj_Close是首条隔夜收益重建元数据。Open/High/Low/Close为供应商已拆股复权价格；Adj_Close进一步包括分配复权。Dividends/Capital_Gains按相同标准化每股单位，Stock_Splits只审计。anomaly_*是原标志，不代表外部核验。schema未强行改写原输入，以保留精确来源和原解析精度。

processed/final_strategy_daily_returns/*.parquet：最终账本每日净收益，Date+25策略列；列名N_<rule>__D_<rule>明确顺序，strategy_catalog.csv同时逐项给出overnight_rule/daytime_rule。收益含初次入场与终止清算，4776行。旧/指数桥梁每日面板只放08/reference_return_panels，属于对照推断的真实输入。

processed/return_panel_catalog.csv列出全部81个模型/ETF/成本逻辑面板的路径与hash。GLD、SLV、USO的9个指数桥梁面板与最终现金账本面板逐字节相同，因此只保留一份实体，由显式映射引用。总计72个实体面板；这不是遗漏9个模型结果，复制校验确认其完全相同。

processed/return_reconciliation.parquet：原缓存与价格重构的逐行差异和usable标志；原始预热行可能没有足够前序值，首个实际交易信号必须可重构并已验收。exchange_schedule.csv为pandas_market_calendars5.4.0的NYSE核心时段代理，UTC开收盘，包括假日、提前收盘与DST；不声称ETF在整个close-to-open期间不交易。

data_manifest.json保存逐源hash、样本、字段和来源限制。audits/保留公司行动与49条异常；异常未删除。原下载时刻未知，本次没有独立供应商下载校验。不得把内部收益恒等式当外部数据正确性的证明。
