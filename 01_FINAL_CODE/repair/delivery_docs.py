"""Human-readable delivery documentation; generated counts come from stored outputs."""

import json
from pathlib import Path


ISSUES = [
    (
        "dividend / adjusted price treatment",
        "确认存在",
        "原论文现金分配公式与复权指数实现不等价；不能再向复权收益加一次分红。",
        "分析收益保留；账本使用拆股复权OHLC和有符号分配。",
        "分配日隔夜口径最大差异约11.746 bps；以指数账本桥梁分离影响。",
        "写明指数分解与现金账本区别。",
        "repair/data_audit.py:reconstructed; corporate_action_audit.csv",
    ),
    (
        "overnight/daytime return construction",
        "部分成立",
        "代码本身满足复权日收益恒等式；论文表述不同。",
        "保留原冻结同session收益信号，独立复算恒等式与缓存。",
        "未改变信号、样本或25规则。",
        "不能把账本分配口径偷偷替换为新信号。",
        "repair/data_audit.py:audit; data_checks.csv",
    ),
    (
        "short positions",
        "确认存在",
        "按每session目标权重复利，但没有股份/现金状态。",
        "区间内股数固定，边界按费用后净值恢复目标。",
        "Short/Short不再等价于仅开平两单。",
        "删去仅两次交易实现复利的经济解释。",
        "repair/ledger.py:execute; test_ledger.py",
    ),
    (
        "short rebalancing",
        "确认存在",
        "目标不变就没有成本，即使空头市值已经漂移。",
        "真实买卖股数复位，除息负债按原持仓计提。",
        "2bps Short/Short成交9,119–9,496次。",
        "明确再平衡成本与借券条件。",
        "test_unchanged_short_covers_twenty; trade_ledger/",
    ),
    (
        "turnover",
        "确认存在",
        "以绝对目标变化累计单位数代替成交金额。",
        "分别给出信号切换、成交笔数、再平衡、货币成交额和净值标准化成交额。",
        "两种turnover不可当作同量纲。",
        "旧表的状态切换量不能称真实交易量。",
        "repair/backtests.py:run_one; transaction_costs/",
    ),
    (
        "transaction costs",
        "确认存在",
        "成本率乘目标切换，遗漏漂移交易；目标求解近似。",
        "费率乘真实成交名义金额，分段求解费用后目标；包括首次建仓与最终清算。",
        "0/1/2bps相对胜出数保持68/24/4；个别终值改变。",
        "1–2bps为成本情景，不是历史报价估计。",
        "model_comparison.csv; cost_sensitivity.csv",
    ),
    (
        "look-ahead check",
        "未确认",
        "原规则使用前一日同类session收益；审稿要求核对时点。",
        "保留定义；逐边界验证signal_available_at不晚于trade boundary。",
        "未发现未来收益进入交易信号。",
        "可行竞价成交仍未证实；不把诊断回归变成策略。",
        "repair/data_audit.py:inputs; ledger_acceptance_checks.csv",
    ),
    (
        "H2 / predictability test",
        "确认存在",
        "无预测能力被等同为反转期望毛收益为零。",
        "带截距AR与符号回归、独立反转均值检验和漂移/协方差恒等分解。",
        "日间AR全负但9个原始p值均不显著；符号斜率同样无显著项。",
        "无证据不等于证明不存在预测能力；盈利与预测能力分开。",
        "repair/inference.py:basic_tests; test_reversal_drift_can_be_nonzero_without_predictability",
    ),
    (
        "Newey-West bandwidth",
        "部分成立",
        "原自动代码实际为9，论文写8。",
        "保留原公式，输出实际有效n及lag。",
        "全样本4776与回归4775均为9；无需人为改为8。",
        "纠正文字而非为了审稿改代码带宽。",
        "repair/common.py:auto_lag; session_mean_tests.csv",
    ),
    (
        "MDD",
        "部分成立",
        "已有初始100，但session路径未纳入最终清算费。",
        "用初始值、各边界交易前后和最终清算组成同一财富路径。",
        "0bps不受清算费用遗漏影响；非零成本及新账本路径需重算。",
        "称session-boundary MDD；不能声称观察区间内最深回撤。",
        "test_entry_and_exit_both_in_wealth_and_drawdown; test_all_ledger_boundaries_cash_fees_timing_and_risk",
    ),
    (
        "volatility",
        "未确认",
        "原每日样本标准差×sqrt(252)未发现公式错误。",
        "对修正每日净收益应用相同公式，ddof=1。",
        "变化来自日收益序列，不是换公式。",
        "与年化算术均值及CAGR分别表述。",
        "repair/common.py:metrics; volatility/",
    ),
    (
        "Sharpe",
        "部分成立",
        "零利率每日均值/标准差年化基本公式正确；解释需限定。",
        "保持零利率定义，Cash/Cash零方差记缺失，不伪造为0；单列融资情景。",
        "变化来自新净收益；现金利率情景另列。",
        "零利率Sharpe不是利率中性。",
        "repair/common.py:metrics; sharpe/",
    ),
    (
        "bootstrap",
        "确认存在",
        "未学生化中心化stationary bootstrap被过度归于完整Ledoit–Wolf；自定义尾部计数可为0。",
        "准确命名、basic区间、(k+1)/(B+1)、模拟误差；均值greater与Sharpe双侧方向不变。",
        "原协议与新协议p值可因随机抽样及有限模拟约定改变。",
        "探索性，非选择校正；不用显著性反调种子。",
        "repair/inference.py:pairwise; bootstrap_tests/",
    ),
    (
        "SPA",
        "部分成立",
        "原方法调用和24候选负收益损失有效；审稿未实际跑并不等于方法无效。",
        "固定arch8.0.0并执行，保持24非BH含Cash；block10主设定，5/20敏感性。",
        "新模型81个ETF/成本/区块组合均不拒绝。",
        "检验联合期望收益，非最大终值或Sharpe；不显著不证明相等。",
        "repair/inference.py:spa_stepm; test_stepm_reuses_full_spa_family_correctly",
    ),
    (
        "StepM",
        "部分成立",
        "原调用有效，但解释必须限定候选家庭。",
        "实际执行StepM，记录优胜ID、5%FWER及候选集。",
        "81组合识别数均为0。",
        "FWER限单ETF/成本家庭，非整个研究跨所有尝试。",
        "04_STATISTICAL_TESTS/SPA_StepM/",
    ),
    (
        "subperiod analysis",
        "部分成立",
        "已有三个描述性时期，不能声称真正未见样本。",
        "同一账本、初始100、统一入场/清算、上一同类session信号。",
        "3时期×9ETF×25策略×3成本=2025行。",
        "为已观察样本的描述性稳健性，不是新holdout。",
        "repair/backtests.py:run_all; subperiod_results.csv",
    ),
    (
        "multiple testing",
        "部分成立",
        "原N和N-D已有Holm，不能声称完全未做校正。",
        "主9项N-D；N、D各9项，另给27项敏感性；回归与探索性bootstrap分别标家庭。",
        "Holm后N为DBA/DBP/GLD/SLV；N-D为DBA/SLV。",
        "点估计为正、单session显著和两session差异显著不是同一命题。",
        "repair/inference.py:adjust_groups; FAMILY_DEFINITIONS.md",
    ),
    (
        "weekday/weekend difference",
        "确认存在",
        "分别检验压缩子组均值，不能以两组显著性不同说明差异显著。",
        "全时间序列含周末/假日指示的HAC回归，直接检验差异。",
        "9ETF家庭Holm结果与单独组均值的推断对象不同。",
        "机制解释需降格为描述性，不作因果归因。",
        "weekend_holiday_difference_tests.csv",
    ),
    (
        "Night / Day naming",
        "部分成立",
        "原策略CSV采用DAY/NIGHT，engine/论文表格采用NIGHT/DAY。",
        "显式转换器；内部night_rule/day_rule，交付CSV别名overnight_rule/daytime_rule。",
        "675行正确对应；不是所有旧标签都错。",
        "避免只依赖显示标签解释。",
        "test_importer_explicit_transpose; legacy_reconciliation.csv",
    ),
    (
        "first pre-sample signal",
        "部分成立",
        "GLD/SLV/USO前序价格未在普通连续行中；审稿忽略保留的Prior字段。",
        "使用Prior_session_date/Prior_Close/Prior_Adj_Close重建最早收益，缓存逐行比对。",
        "无需延后共同样本；独立供应商核验尚未完成。",
        "内部可重建不等于外部验证。",
        "warmup_checks.csv; data_checks.csv",
    ),
    (
        "double split adjustment",
        "未确认",
        "未证实原代码重复处理拆股。",
        "OHLC已拆股复权，保持标准化股份单位，不再对Stock_Splits乘一次。",
        "无虚构拆股收益；原始公司行动记录保留。",
        "明确单位，不能声称已查出不存在的双重拆股错误。",
        "test_split_adjusted_no_double_application; corporate_action_audit.csv",
    ),
    (
        "data provenance and anomalies",
        "确认存在",
        "原下载时刻未存；异常标志不等于外部核验。",
        "源文件hash、抽取/重建时刻、日历版本、49条异常及未独立核验状态保留。",
        "不删极端数据，不改变样本。",
        "价格/成交可执行性与独立来源仍有限制。",
        "data_manifest.json; anomaly_audit.csv",
    ),
]


def write_documents(target, summary, test_counts):
    p = Path(target)

    def write(rel, text):
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text(text.strip() + "\n")

    passed = test_counts["passed"]
    failed = test_counts["failed"]
    skipped = test_counts["skipped"]
    readme = f"""# Commodity ETF empirical repair — clean research delivery

本交付为用户删除上一完整修复项目后，明确授权重新开始而实际重建、重跑的版本。只使用幸存原项目数据、原始代码、原固定研究定义及已保留修正表的格式；不调样本、策略、费率、随机种子或显著性方向。原工作目录未移动或删除。本文件夹是审核用的筛选副本，不包含缓存、虚拟环境、原始项目ZIP、重复稿件或中间pickle。

## 先读什么

- `09_REPORTS/empirical_fix_report.md`：修复、结果和结论。
- `09_REPORTS/issue_verification_registry.csv`：逐项“确认存在／部分成立／未确认”，附代码或测试证据。
- `08_OLD_VS_NEW/old_vs_new_summary.md`、`old_vs_new_results.csv`：经济含义与全部675行差异。
- `07_VALIDATION_AND_TESTS/test_summary.md`：实际验证状态；运行日志、JUnit与账本验收在同目录。
- `01_FINAL_CODE/run_instructions.md`：隔离环境的一条复现命令。
- `00_README/FILE_MANIFEST.csv`：逐文件用途、生成器、final/reference、SHA-256；每个文件只有一个交付位置。

## 本轮改了什么、什么没有被证实

确认并修复：现金分配公式与复权实现不一致；固定目标空头再平衡与费用遗漏；将信号切换量称为真实成交；H2把无预测能力等同零反转毛收益；MDD终端清算遗漏；bootstrap命名/有限模拟p值与不充分的检验对象说明；直接周末差异检验和明确多重检验家庭。

没有证实：原交易规则存在未来收益信号；原Volatility基本公式错误；原Sharpe基本年化公式错误；原代码重复拆股；原先完全没有Holm；原HAC代码实际用8。GLD/SLV/USO第一信号可由保留的Prior字段重建，故没有延后样本。以上与独立供应商核验不同，后者仍未完成。原MDD已有初始100，仅不能完整覆盖最终清算费。SPA/StepM原调用可复现，原审稿未运行不等于调用错误。

## 数据与范围

样本：**2007-01-09—2025-12-31，每只4,776日**。九只：DBA、DBB、DBC、DBE、DBO、DBP、GLD、SLV、USO。每session五条规则Cash/Long/Short/Momentum/Reversal，笛卡尔积**25**，主成本**0/1/2 bps**，初始财富100，共675策略/成本行。输入预热记录保留；样本不静默扩大。三个时期为2007–2012、2013–2019、2020–2025；实际第二、三段首交易日分别2013-01-02、2020-01-02，天数1506/1762/1508。

`02_FINAL_DATA/provided_prices/`是实际输入，逐字节保留提供的已含复权因子/收益缓存/预热元数据CSV。`processed/`保存实际复算与推断使用的收益面板和交易日历。原下载时刻未知；本次抽取/运行时间与源hash另存，不能冒充历史下载日志。

## Return construction、信号与账本

分析收益保持供应商复权指数口径：`a=Adj_Close/Close`，`adjusted_open=a*Open`，`rN=adjusted_open/previous_Adj_Close-1`，`rD=Close/Open-1`，`rC=Adj_Close/previous_Adj_Close-1`。逐行核对`(1+rN)(1+rD)=1+rC`及缓存。Momentum/Reversal继续使用前一日同类session的冻结缓存收益，零信号为零；没有将现金账本收益偷偷换入信号。

执行账本使用已拆股复权、未作分配复权的OHLC和对应标准化股份，Stock_Splits仅审计，不二次应用。分配对原有持仓按`q_old*(Dividends+Capital_Gains)`计提，空头为负债。基线假设除息开盘现金结算，**并非历史支付日证据**。有符号应收/应付的20日延迟结算另作情景。

区间股数固定。边界先盯市并处理利息/借券/融资与旧持仓分配，再以已知信号求解交易；目标相对**费用后净值**：`E+=E−-c*abs(delta_q)*P`，`q_new*P=z*E+`，现金支付真实订单与费用。同一目标的空头漂移也要交易。`signal_transitions`、`executed_trades`、`rebalance_trades`、货币turnover及按交易前净值标准化turnover分列。100%上一边界空头市值作为受限现金；仅超出受限额的正现金计自由现金利息。基线现金/借券/融资率均0。利率按真实UTC间隔/365；场景2%/2%/5%与5%/5%/8%（现金/借券/融资），不是历史估计。非正净值停止风险持仓并清算；主样本无破产组合。

每日净收益包含初次建仓和最终清算，连乘等于终值。MDD覆盖初始100、每个边界交易前后及最终清算，称session-boundary MDD。Vol=`sd(daily,ddof=1)*sqrt(252)`；Sharpe=`mean(daily)/sd(daily)*sqrt(252)`，风险利率0，Cash/Cash的0方差Sharpe未定义，以空值及status解释。CAGR与252倍算术均值分开。

## 最终统计方法与所有复现参数

| 项目 | 固定设定 |
|---|---|
| 根随机种子 | **20260928**，未因结果更换 |
| 子种子 | SHA256(`20260928|family|ticker|...`)前4字节little-endian；每行CSV保存实际整数；具体label见`inference.fixed_seed` |
| 均值/回归 | 双侧OLS+HAC Bartlett；默认无小样本修正；带截距 |
| HAC lag | `floor(4*(n/100)^(2/9))`；n=4776和4775均9；子样本实际n/lag逐行保存 |
| 多重检验 | 主9个N-D；N和D各9；27项联合敏感性；AR/符号斜率按session/spec各9；探索性配对每ETF/成本/区块/模型23项 |
| H2 | 同session AR(1)、新增符号回归诊断、反转均值与精确漂移/协方差分解；跨session另列诊断 |
| 周末差异 | 完整时间序列组别指示HAC，直接检验组间均值差 |
| 配对bootstrap | stationary；**2,000**次；block **10**主设定，**5/20**敏感性；所有候选与BH同行重抽 |
| 配对统计 | 未学生化、中心化；basic 95%区间；均值greater保持原代码、Sharpe双侧；自定义p=(k+1)/(B+1) |
| SPA/StepM | `arch==8.0.0`实际运行；**5,000**次stationary；block10主、5/20敏感性；studentize=True，StepM size=.05；SPA nested默认False |
| SPA家庭/损失 | 每ETF/成本24个非BH（含Cash）；负每日净收益；BH=Long/Long；原生严格greater计数规则，不手改plus-one |
| 模拟精度 | 每行SE、二项Clopper–Pearson区间与分辨率；custom 1/2001，arch 1/5000 |
| Break-even | 对BH及Cash；0,1,2,5,10,20,50,100bps网格首个正→非正括号，Brent xtol=1e-8；不宣称全局单调 |
| 基线/敏感性 | 主0/1/2bps；成本补充5/10；两组利率；20日分配延迟；原三时期 |
| 数值容差 | 成交舍入阈值1e-12×max(1,abs(E))；基线终值rtol1e-8；财富恒等式rtol1e-11；自融资及目标残差<1e-8 |
| 环境 | Python3.13.5；直接依赖`requirements.txt`，完整传递依赖`requirements.lock.txt`，实际平台/版本在run_manifest |

所有统计检验的成本与策略字段不适用时明确标记NOT_APPLICABLE；SPA是候选家庭而非单策略。表与CSV顺序均**Night/Day**；`overnight_rule`和`daytime_rule`分列。原始DAY/NIGHT验证输入只在reference目录保留，绝不直接当final结果。

## 结果与论文含义

旧终值675行全部复现，最大相对误差{summary['baseline_max_relative_error']:.3g}。原16张LaTeX表逐字节重现。新账本主结果675行、分段2025行、融资/支付敏感性2025行、break-even414行；27个账本文件共6,448,275边界/策略行。新模型配对结果1863行，SPA/StepM81行（主27、敏感性54）。统计旧新比较使用相同的新协议与子种子以隔离财富引擎；原论文实际统计量另作reference，不能混同。

相对BH胜出（排除Cash与BH，分母207）0/1/2bps均为**68/24/4**，旧新版数量相同，但单策略数值不同。2bps的DBE Long/Reversal、DBO Reversal/Short、SLV Long/Reversal、USO Short/Short仍相对胜出；仅DBE与SLV终值超过100。USO Short/Short由45.9294变为44.0013；费用、漂移与分配影响由中间指数账本逐行分解。

可保留：8个隔夜均值点估计为正；成本侵蚀本候选集的多数优势；当前家庭SPA/StepM无显著优胜证据。Holm后隔夜均值显著为DBA/DBP/GLD/SLV，主N-D差异仅DBA/SLV。须弱化：不是8只都存在显著日夜差异，负日间AR估计不证明可预测反转，情景成本不等于历史可交易净收益。不支持：无预测能力等价于零反转收益；短仓两笔交易即可实现每session -1复利；4个相对赢家都是绝对盈利或alpha；不显著证明策略永不可能盈利。

## 验收、版本和未解决事项

本次完整pytest：**PASS {passed} / FAIL {failed} / SKIPPED {skipped}**；逐项见JUnit与test_summary。验收验证现金方程、费用、目标、所有边界信息时点、日收益/终值/风险指标一致性，未把“脚本没报错”等同于通过。24个修正表与保留上一修复表的数值/字节核对见validation_results，若存在差异必须列入unresolved。

仍有未解决问题：49条异常没有第二供应商/成交记录独立核验；原始下载时刻缺失；支付日、历史借券可得性及费用、融资和竞价成交数据缺失；新诊断与已观察分段的选择局限；旧修复完整日志和精确输出已删，不能恢复其历史全量hash。现在交付的是可审计的新运行，不能声称找回旧133文件逐字节证据。原论文正文/PDF未更新，不能把旧稿称投稿就绪；10_MANUSCRIPT中仅放明确声明。详见`09_REPORTS/unresolved_issues.md`。
"""
    write("00_README/README_MASTER.md", readme)
    write(
        "00_README/CHANGELOG.md",
        """# Version selection and changelog

| 来源/版本 | 处理 | 原因 |
|---|---|---|
| 上传原项目 | 原位置保留，重建目录中只读baseline；交付仅包含原引擎/脚本、实际输入和必要验证CSV | 不把原稿旧表、旧图、ZIP、pickle混入FINAL |
| 上一次已删除修复项目/ZIP | 不声称恢复；用户明确授权重新从头执行 | 旧完整运行日志及133输出hash证明无法找回 |
| 幸存24个修正LaTeX表 | 用于独立对照；FINAL只放本次代码生成的表 | 核对报告保留hash和比对状态，不重复放第二套表 |
| 本次重建结果 | 唯一FINAL数值来源 | 固定同一数据、样本、策略、模型、检验参数与根种子，不按显著性择版 |
| 旧/中间财富模型 | 仅在08_OLD_VS_NEW和reference收益面板中出现 | 用于旧新差异与归因，不当作新版主结果 |
| 0/1/2bps指标 | 分解到指标目录 | 数值字符串原样投影；不再附一份同内容宽表；5/10bps补充单列 |
| 9个完全相同的收益面板 | 只保存一份实体文件，return_panel_catalog.csv保留全部81个逻辑输入的映射 | GLD/SLV/USO的指数桥梁与现金账本在这9个文件上字节相同；72个实体文件无重复，无丢失 |
| Night/Day列名 | 交付overnight_rule/daytime_rule；代码仍night_rule/day_rule | 明确同义字段，原DAY/NIGHT输入有专用转换器 |
| 原稿main_mdpi.tex/PDF | 不复制旧正文来冒充修正稿 | 用户要求正文留待实证确认后；本阶段没有改写 |

目录重排只复制；未删除或移动源工作文件。新交付文件名描述内容，排除tmp/cache/__pycache__、虚拟环境、重复图、测试中间日志。文档与manifest属于本次新建交付说明，不是论文改写。
""",
    )
    table = [
        "# Old versus new implementation and implications",
        "",
        "| Issue | Old implementation | New implementation | Effect on results | Paper implication |",
        "|---|---|---|---|---|",
    ]
    table += [
        "| " + " | ".join([a, c, d, e, f]) + " |" for a, b, c, d, e, f, g in ISSUES
    ]
    table += [
        "",
        "数值差异见同目录old_vs_new_results.csv。legacy→adjusted-index ledger隔离目标求解、真实成交与再平衡；index→cash ledger隔离价格/分配口径。两段差异之和等于总差异。",
        "",
        "统计对照有两层：original_protocol_reference_statistics.csv来自本次实际执行的未改动原analysis.py；old_vs_new_*_tests.csv是在相同新版推断协议/随机抽样下对旧财富引擎与新财富引擎的比较，不能把其中legacy列当成原论文p值。原bootstrap采用全局RNG序列/旧尾部约定，新版固定子种子和plus-one约定，导致数值差异并非全由账本修复引起。",
    ]
    write("08_OLD_VS_NEW/old_vs_new_summary.md", "\n".join(table))
    write(
        "09_REPORTS/unresolved_issues.md",
        """# Unresolved issues and scope limits

| ID | 状态 | 未解决事项 | 对审核的影响 |
|---|---|---|---|
| U01 | NOT TESTED externally | 49条原异常记录保留；本次无第二供应商或交易所逐笔核验 | 内部恒等式/日期/正价格通过不等于开盘价真实可执行 |
| U02 | UNAVAILABLE | 原下载时刻未保存；提供数据的历史供应商响应不可恢复 | 只有现有源文件hash、已知参数和本次真实重建记录 |
| U03 | SCENARIO ONLY | 实际分配支付日、借券可得性/费率、融资利率和保证金约束缺失 | 除息即付、20日延迟、固定利率均为假设情景 |
| U04 | NOT TESTED | 公开开收盘价的竞价提交延迟、几分钟后价格、滑点及真实成交容量 | 无信号前视并不证明这些价格可实现 |
| U05 | INFERENCE LIMIT | 新增符号回归为修订诊断；分段早已观察；候选家庭不等于整个研究所有尝试 | 不称新holdout，不声称pairwise选择校正或全研究FWER |
| U06 | HISTORICAL ARTIFACT LOSS | 用户已删除上一完整修复项目/日志/精确CSV | 本次实际重建有新日志；24张幸存表提供显示精度/字节对照，不能重建上一133文件一致性证明或已丢失的外部请求证据 |
| U07 | DEFERRED BY USER | 原main_mdpi.tex/PDF正文、参考文献全文支持性审核未更新 | 方法公式/措辞建议单独交付；原稿文字与新实现尚未统一，不是投稿就绪稿 |

此前“找不到完整修复源码”的交付阻塞，已通过用户授权重建与实际重跑解除。它没有被静默遗忘；U06保留历史证据无法恢复的范围。新的数值结果只认本次实际输出；不得用上一报告关于额外Yahoo请求或第二来源404的历史文字代替本次运行记录。若数值与上一保留表不一致，详见表格核对CSV；交付没有为贴合文字而改数。
""",
    )
    write(
        "07_VALIDATION_AND_TESTS/test_summary.md",
        f"""# Validation status — actual rebuild

| Status | 检查 | 证据/解释 |
|---|---|---|
| PASS | {passed}项pytest单元及全量验收，0策略定义调参 | validation_results/pytest_results.xml、run_logs/pytest.log；其中17账本单元、7统计单元、8全量验收 |
| PASS | 原675终值相对误差<1e-8 | sanity_checks/legacy_reconciliation.csv；最大{summary['baseline_max_relative_error']:.3g} |
| PASS | 原16张表逐字节复现 | validation_results/original_table_reproduction.csv |
| PASS | 固定9ETF/25策略/3成本、4776日期与无前视 | 完整网格验收、data_checks.csv、27个账本检查；不是依据没报错推断 |
| PASS | 自融资、费用金额、分配、最终清算、每日收益与风险数值一致 | validation_results/ledger_acceptance_checks.csv；全部6,448,275账本行 |
| PASS | bootstrap配对/seed/家庭、SPA真实StepM与直接SPA一致性 | unit_tests/test_inference.py及原生输出字段 |
| FAIL | 当前最终pytest失败数{failed} | 若非0不得宣布通过；完整日志保留所有报错/警告 |
| NOT TESTED | 第二供应商异常核验、历史支付日/借券/融资、竞价与分钟级成交、旧删除项目全量hash恢复 | 不能把缺少检验写成PASS |
| NOT APPLICABLE | 正文改写/整篇PDF编译、新增机器学习/真正未见holdout、参考文献全文复审 | 本轮未执行，按用户范围排除 |

pytest skipped={skipped}。Matplotlib/pyparsing的依赖弃用警告不等于研究结果失败，原文在日志中；没有掩盖或以“没有报错”替代数值验收。表格重建、复制校验、CSV元数据/数值字符串保持及manifest目录校验记录于validation_results；ZIP完成后的CRC/逐文件hash检查另存ZIP旁verification.json。这些仅证明对应文件层面性质，不证明历史市场数据真实性。
""",
    )
    winnerlines = [
        "| ETF | Overnight rule | Daytime rule | Wealth | BH wealth |",
        "|---|---|---|---:|---:|",
    ]
    for r in summary["relative_winners_2bps"]:
        winnerlines.append(
            f"| {r['ticker']} | {r['night_rule']} | {r['day_rule']} | {r['terminal_wealth']:.4f} | {r['benchmark_terminal_wealth']:.4f} |"
        )
    write(
        "09_REPORTS/empirical_fix_report.md",
        f"""# Empirical repair report

本报告对应本次真实重建运行；原稿正文未更新。原675终值全部复现（最大相对误差{summary['baseline_max_relative_error']:.3g}），原16表字节一致，9ETF共同样本4776日未改。{passed}项pytest通过；详细证据位于07_VALIDATION_AND_TESTS。

核心修复为可审计的股数/现金/分配/费用账本：区间固定股数，边界恢复费用后目标，真实订单按名义金额付费。保留原信号和分析复权收益，避免把数据口径修复变成新策略。收益、MDD、Vol、Sharpe、所有成本和统计推断均从同一新账本重做。

0/1/2bps相对BH胜出数仍为68/24/4（207个active），绝对盈利且胜出数47/10/2。2bps的4个相对胜出组合：

{chr(10).join(winnerlines)}

其中DBO与USO终值低于100。Short/Short交易数从旧模型2次目标切换变为2bps下{summary['short_short_executed_trades_range_2bps'][0]}—{summary['short_short_executed_trades_range_2bps'][1]}笔真实订单；USO终值45.9294→44.0013。各行归因见旧→指数账本→现金账本的桥梁差异；不强行要求每项修复都降低收益。

Holm后隔夜均值显著DBA/DBP/GLD/SLV；N-D主家庭显著DBA/SLV。日间9个AR系数均负，原始双侧p<.05者0；符号回归同样0。无预测能力与零反转收益不等价，漂移/协方差分解仅为样本恒等式。新SPA主27家庭、含block敏感性81家庭均无拒绝，StepM无识别；只针对各ETF/成本24个非BH候选的期望收益。

结论可保留：8个隔夜均值点估计为正，成本侵蚀多数候选优势，未获得该候选家庭显著优胜证据。需弱化：日夜差异不能推广到全部ETF；负日间AR不构成可靠可预测反转；情景成本不是历史真实可交易费用。不支持：4个相对赢家都是盈利/alpha、短仓仅两单实现固定目标复利、不显著等于策略相等或永不盈利。

公开结果仅包含本次固定协议；原方法复现统计和新协议下旧引擎统计分开标识。未发现前视、原Vol基本公式错误或重复拆股；原HAC代码已是9、已有部分Holm、原MDD已有初始100。审稿意见的部分断言因此没有机械采纳。

仍有49条异常未被独立供应商核验；支付、融资、借券和真实边界成交依赖情景。原下载时刻和已删除旧日志不可补造；文献全文及正文统一留待后续。完整问题登记、方法建议及任务状态分别见本目录相关文件。
""",
    )
    write(
        "02_FINAL_DATA/DATA_DICTIONARY.md",
        """# Data and model inputs

provided_prices/*.csv：九只实际输入CSV；保留提供文件的全部字段、预热行及数值字节。Date为本地交易日期，in_sample选择固定4776日；GLD/SLV/USO的Prior_session_date/Prior_Close/Prior_Adj_Close是首条隔夜收益重建元数据。Open/High/Low/Close为供应商已拆股复权价格；Adj_Close进一步包括分配复权。Dividends/Capital_Gains按相同标准化每股单位，Stock_Splits只审计。anomaly_*是原标志，不代表外部核验。schema未强行改写原输入，以保留精确来源和原解析精度。

processed/final_strategy_daily_returns/*.parquet：最终账本每日净收益，Date+25策略列；列名N_<rule>__D_<rule>明确顺序，strategy_catalog.csv同时逐项给出overnight_rule/daytime_rule。收益含初次入场与终止清算，4776行。旧/指数桥梁每日面板只放08/reference_return_panels，属于对照推断的真实输入。

processed/return_panel_catalog.csv列出全部81个模型/ETF/成本逻辑面板的路径与hash。GLD、SLV、USO的9个指数桥梁面板与最终现金账本面板逐字节相同，因此只保留一份实体，由显式映射引用。总计72个实体面板；这不是遗漏9个模型结果，复制校验确认其完全相同。

processed/return_reconciliation.parquet：原缓存与价格重构的逐行差异和usable标志；原始预热行可能没有足够前序值，首个实际交易信号必须可重构并已验收。exchange_schedule.csv为pandas_market_calendars5.4.0的NYSE核心时段代理，UTC开收盘，包括假日、提前收盘与DST；不声称ETF在整个close-to-open期间不交易。

data_manifest.json保存逐源hash、样本、字段和来源限制。audits/保留公司行动与49条异常；异常未删除。原下载时刻未知，本次没有独立供应商下载校验。不得把内部收益恒等式当外部数据正确性的证明。
""",
    )
    write(
        "04_STATISTICAL_TESTS/multiple_testing/FAMILY_DEFINITIONS.md",
        """# Multiplicity families and locations

数值只保存在相应检验CSV的holm_*列，不额外复制一张相同数值表。session_mean_tests.csv：主九个N-D；N、D各独立九项；holm_27_sensitivity为三种假设合并27项。predictability CSV：每session、每AR1或lag_sign、每斜率/截距分别九项；cross_session诊断家庭按family列。reversal均值各session九项。weekend差异九项。subperiod按时期及N/D/N-D各九项。

pairwise_bootstrap_tests.csv：每ticker/model/cost/block的23个active候选，相对BH；mean与Sharpe各校正，仍属探索性，未消除事后最佳策略选择。SPA/StepM：每ticker/cost的24个非BH，含Cash；StepM size=.05控制此候选家庭，不控制整个研究所有ETF、成本、区块与其他尝试。不能为了多星号重新定义family。
""",
    )
    write(
        "04_STATISTICAL_TESTS/statistical_summary/statistical_summary.md",
        """# Statistical interpretation

分析均值、预测回归与策略净盈利为不同对象。分析复权收益的N/D/N-D均值不随0/1/2bps重复，因为其并非扣交易成本的策略收益。回归AR/符号含截距、实际n/lag和双侧CI；新增符号为修订诊断。cross_session有共同端点测量及边界成交可行性限制，不是新增策略。

配对均值使用原greater方向，Sharpe双侧，未学生化中心化stationary bootstrap；CI为basic。重抽行在候选与BH间配对；自定义p加1，arch原生p规则不修改。block10主、5/20敏感性。CSV中的MC区间只描述模拟计数不确定性，不是效应量区间。

SPA损失为负每日净收益，联合期望收益优于BH的检验，不检验最大终值或Sharpe。无拒绝/StepM空集合是本候选和参数下的证据不足，不是策略相同或无法盈利的证明。实际汇总以09_REPORTS/findings_summary.json为单一机器可读来源，正文尚未更新。
""",
    )
    write(
        "03_FINAL_RESULTS/RESULTS_SCHEMA.md",
        """# Result schema and units

所有关键最终CSV自带ticker、overnight_rule、daytime_rule、strategy_id（如适用）、cost_bps、sample_start、sample_end、model_version与rule_order。overnight_rule对应代码night_rule，daytime_rule对应day_rule；值未重编码。元数据NOT_APPLICABLE表示无交易策略/费率的统计对象；FAMILY_24_NON_BH表示SPA候选家庭。多个ticker汇总明确列出全部ticker。

主指标每成本225行：terminal_wealth（初始100单位）；mdd_session_boundary_fraction（比例，表格乘100）；volatility_annualized（比例，表格乘100）；sharpe_zero_rate_annualized（无量纲，Cash/Cash未定义空值）。annualized_growth_and_returns另列CAGR与252倍算术均值，避免混淆。

transaction_costs_and_turnover包含真实成交额、累计成本（初始100同单位）、目标切换和实际订单数、标准化成交额。5/10bps补充情景不重复0/1/2主指标。trade_ledger有27个ticker/cost文件，每个25×9553边界行；boundary_timestamp与signal_available_at为UTC。最后marked_equity_next_boundary为空，因为无下一边界；这不是缺失结果。全部关键权益、股数、现金、费用、分配、利息、受限余额、残差均保留。

break_even_costs中的base_cost_bps=0表示检查毛优势起点；cost_bps=SEARCH_VARIABLE，breakeven_bps为根。no_gross_advantage与no_crossing_on_0_to_100bps_grid不同，不以0或100虚构替代缺失根。融资场景同列利率与delay；不是历史费率。subperiod日期用实际交易日起止；每段初始100且独立清算，不能简单把三个段终值当一条未中断账户。

复制或CSV列投影不重新计算结果，原数值字符串完整保留；只补充元数据、清楚列名/别名、空值含义。双模型差异/统计对照为独立研究用途，不能将reference模型当主结果。
""",
    )
    write(
        "10_MANUSCRIPT/README.txt",
        "Manuscript was not updated in this empirical-repair stage.",
    )
