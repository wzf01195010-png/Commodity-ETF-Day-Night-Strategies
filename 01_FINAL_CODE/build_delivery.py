"""Curate completed native outputs by copying/projecting fields, never by rerunning analysis."""

import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import sys
import xml.etree.ElementTree as ET
from repair.delivery_docs import ISSUES, write_documents

TICKERS = ["DBA", "DBB", "DBC", "DBE", "DBO", "DBP", "GLD", "SLV", "USO"]
LEDGER = "ledger_split_adjusted_cash_ex_open"
ALIASES = {
    "night_rule": "overnight_rule",
    "day_rule": "daytime_rule",
    "period_start": "sample_start",
    "period_end": "sample_end",
    "MDD": "mdd_session_boundary_fraction",
    "Vol": "volatility_annualized",
    "SR": "sharpe_zero_rate_annualized",
}


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_csv(path, rows, fields=None):
    rows = list(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--method-notes", type=Path, required=True)
    args = parser.parse_args()
    project = args.project.resolve()
    out = project / "outputs"
    target = args.target.resolve()
    if target == project or project in target.parents:
        raise ValueError("Delivery must be independent of source project.")
    target.mkdir(parents=True, exist_ok=True)
    folders = [
        "00_README",
        "01_FINAL_CODE",
        "02_FINAL_DATA",
        "03_FINAL_RESULTS/terminal_wealth",
        "03_FINAL_RESULTS/mdd",
        "03_FINAL_RESULTS/volatility",
        "03_FINAL_RESULTS/sharpe",
        "03_FINAL_RESULTS/transaction_costs",
        "03_FINAL_RESULTS/break_even_costs",
        "03_FINAL_RESULTS/subperiod_results",
        "03_FINAL_RESULTS/other_final_results",
        "04_STATISTICAL_TESTS/session_mean_tests",
        "04_STATISTICAL_TESTS/predictability_tests",
        "04_STATISTICAL_TESTS/bootstrap_tests",
        "04_STATISTICAL_TESTS/SPA_StepM",
        "04_STATISTICAL_TESTS/multiple_testing",
        "04_STATISTICAL_TESTS/statistical_summary",
        "05_LATEX_TABLES",
        "06_FIGURES",
        "07_VALIDATION_AND_TESTS/unit_tests",
        "07_VALIDATION_AND_TESTS/validation_results",
        "07_VALIDATION_AND_TESTS/sanity_checks",
        "08_OLD_VS_NEW",
        "09_REPORTS",
        "10_MANUSCRIPT",
    ]
    for folder in folders:
        (target / folder).mkdir(parents=True, exist_ok=True)
    records = {}
    copy_checks = []
    projection_checks = []

    def register(rel, description, generated_by, role="final", source="", notes=""):
        records[rel] = dict(
            category=rel.split("/")[0],
            filename=Path(rel).name,
            relative_path=rel,
            description=description,
            generated_by=generated_by,
            final_or_reference=role,
            notes=notes,
            source_path=str(source),
        )

    def copy(src, rel, description, generated_by, role="final", notes=""):
        src = Path(src)
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        before, after = digest(src), digest(dst)
        assert before == after
        copy_checks.append(
            dict(
                relative_path=rel,
                source_sha256=before,
                delivery_sha256=after,
                status="PASS",
            )
        )
        register(rel, description, generated_by, role, src, notes)

    def project_csv(
        srcname,
        rel,
        description,
        generated_by,
        fields=None,
        keep=lambda r: True,
        role="final",
        extra=None,
        rename=None,
    ):
        src = out / (srcname + ".csv")
        with src.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            source_fields = reader.fieldnames
            source = [r for r in reader if keep(r)]
        selected = fields or source_fields
        aliases = {**ALIASES, **(rename or {})}
        if srcname == "subperiod_session_tests":
            aliases["period_start"] = "requested_period_start"
        rows = []
        preserved = 0
        for original in source:
            r = {aliases.get(k, k): original[k] for k in selected}
            for k in selected:
                assert r[aliases.get(k, k)] == original[k]
                preserved += 1
            # Descriptive metadata only; original numeric tokens remain byte-exact.
            r.setdefault("ticker", "ALL_NINE:" + ",".join(TICKERS))
            r.setdefault("overnight_rule", "NOT_APPLICABLE")
            r.setdefault("daytime_rule", "NOT_APPLICABLE")
            r.setdefault("cost_bps", "NOT_APPLICABLE")
            r.setdefault("sample_start", original.get("period_start", "2007-01-09"))
            r.setdefault("sample_end", original.get("period_end", "2025-12-31"))
            r.setdefault(
                "model_version",
                (
                    "analytical_adjusted_return"
                    if rel.startswith("04_")
                    else "audit_or_summary"
                ),
            )
            r["rule_order"] = "NIGHT/DAY"
            r["cost_definition"] = (
                "NOT_APPLICABLE"
                if r["cost_bps"] == "NOT_APPLICABLE"
                else "scenario_bps_per_actual_traded_notional; legacy_columns_use_signal_switch_cost"
            )
            if srcname == "subperiod_session_tests":
                # Keep the requested nominal boundary; state actual first trading day separately.
                r["requested_period_start"] = r["sample_start"]
                r["sample_start"] = {
                    "2013-01-01": "2013-01-02",
                    "2020-01-01": "2020-01-02",
                }.get(r["sample_start"], r["sample_start"])
            if srcname == "predictability_tests" or srcname == "reversal_decomposition":
                r["estimation_start"] = (
                    "2007-01-09" if original.get("n") == "4776" else "2007-01-10"
                )
            if extra:
                r.update(extra(original) if callable(extra) else extra)
            rows.append(r)
        assert rows, srcname
        write_csv(target / rel, rows)
        projection_checks.append(
            dict(
                relative_path=rel,
                source_filename=src.name,
                source_sha256=digest(src),
                source_rows_selected=len(rows),
                source_fields_projected="|".join(selected),
                field_aliases=json.dumps(aliases, ensure_ascii=False),
                preserved_source_cells=preserved,
                status="PASS",
                notes="Read/write with csv strings; no floating-point recomputation. Added metadata/explicit field aliases only.",
            )
        )
        register(
            rel,
            description,
            generated_by,
            role,
            src,
            "Numerical strings preserved; metadata added. See csv_projection_checks.csv.",
        )

    # Code and exact environment; no cache, virtualenv, compiled bytecode, or copied notebook outputs.
    for f in sorted((project / "repair").glob("*")):
        if f.suffix in [".py", ".json"]:
            copy(
                f,
                "01_FINAL_CODE/repair/" + f.name,
                "实际修复、推断、表图或交付模块/静态格式定义",
                "authored repair source",
            )
    for name in [
        "run_reproduction.py",
        "build_delivery.py",
        "check_delivery.py",
        "requirements.txt",
        "requirements.lock.txt",
        "config.json",
    ]:
        copy(
            project / name,
            "01_FINAL_CODE/" + name,
            "复现入口、打包入口或固定配置/依赖",
            "actual rebuild configuration",
        )
    for f in sorted((project / "code").glob("*.py")):
        copy(
            f,
            "01_FINAL_CODE/legacy_reference/" + f.name,
            "未改动原分析脚本；用于基线复现/信号定义",
            "uploaded source archive",
            "reference",
        )
    for f in sorted((project / "tests").glob("test_*.py")):
        copy(
            f,
            "07_VALIDATION_AND_TESTS/unit_tests/" + f.name,
            "最终实际执行单元/验收测试",
            "pytest suite",
        )
    for t in TICKERS:
        files = [
            f
            for f in (project / "data").rglob(t + "_daily.csv")
            if "__MACOSX" not in f.parts
        ]
        assert len(files) == 1
        copy(
            files[0],
            f"02_FINAL_DATA/provided_prices/{t}_daily.csv",
            "实际冻结输入，含价格、行动、缓存收益与预热元数据",
            "provided Yahoo CSV; no new download",
        )
        copy(
            project / "Commodity_ETFS" / f"{t}_25_strategies_2007_2025.csv",
            f"08_OLD_VS_NEW/legacy_validation_inputs/{t}_25_strategies_2007_2025.csv",
            "675原终值验证输入；原始标签DAY/NIGHT",
            "uploaded source archive",
            "reference",
            "Unmodified reference input, not a final result schema; import explicitly transposes DAY/NIGHT.",
        )
    copy(
        out / "data_manifest.json",
        "02_FINAL_DATA/data_manifest.json",
        "数据来源、hash、样本与日历版本",
        "repair.data_audit.audit",
    )
    copy(
        out / "return_reconciliation.parquet",
        "02_FINAL_DATA/processed/return_reconciliation.parquet",
        "所有可用行的原缓存/重建收益差异",
        "repair.data_audit.audit",
    )
    copy(
        out / "exchange_schedule.csv",
        "02_FINAL_DATA/processed/exchange_schedule.csv",
        "含DST及提前收盘的UTC核心交易时间",
        "pandas_market_calendars 5.4.0 / repair.data_audit.audit",
        notes="Calendar input, not a strategy result; ticker/rules/cost do not apply.",
    )
    final_panels = {
        digest(f): "02_FINAL_DATA/processed/final_strategy_daily_returns/" + f.name
        for f in (out / "daily").glob("*" + LEDGER + "*.parquet")
    }
    panel_catalog = []
    for f in sorted((out / "daily").glob("*.parquet")):
        rel = (
            "02_FINAL_DATA/processed/final_strategy_daily_returns/"
            if LEDGER in f.name
            else "08_OLD_VS_NEW/reference_return_panels/"
        ) + f.name
        ticker, model, cost = f.stem.split("__")
        h = digest(f)
        actual = final_panels.get(h, rel) if LEDGER not in f.name else rel
        if actual != rel:
            redundant = target / rel
            if redundant.exists():
                assert digest(redundant) == h
                redundant.unlink()  # Only this exact redundant delivery copy, never source.
        else:
            copy(
                f,
                rel,
                "每日净收益面板；推断真实使用输入，策略列N_...__D_...",
                "repair.backtests.run_all",
                "final" if LEDGER in f.name else "reference",
            )
        panel_catalog.append(
            dict(
                ticker=ticker,
                model_version=model,
                cost_bps=cost.removesuffix("bps"),
                sample_start="2007-01-09",
                sample_end="2025-12-31",
                n=4776,
                overnight_rule="PER_COLUMN_SEE_STRATEGY_CATALOG",
                daytime_rule="PER_COLUMN_SEE_STRATEGY_CATALOG",
                rule_order="NIGHT/DAY",
                data_path=actual,
                sha256=h,
                storage_status=(
                    "byte_identical_alias_of_final_panel"
                    if actual != rel
                    else "unique_physical_file"
                ),
                source_filename=f.name,
            )
        )
    write_csv(
        target / "02_FINAL_DATA/processed/return_panel_catalog.csv", panel_catalog
    )
    for f in sorted((out / "trade_ledger").glob("*.parquet")):
        copy(
            f,
            "03_FINAL_RESULTS/transaction_costs/trade_ledger/"
            + f.stem
            + "_trade_ledger_2007_2025.parquet",
            "完整最终股份/现金/费用/分配与时点账本",
            "repair.backtests.run_all",
            notes="night_rule=overnight_rule; day_rule=daytime_rule. Includes every 9553 boundary for each of 25 strategies.",
        )
    for src, rel, desc in [
        (
            "corporate_action_audit",
            "02_FINAL_DATA/audits/corporate_action_audit.csv",
            "所有分配/拆股及隔夜口径差异",
        ),
        (
            "anomaly_audit",
            "02_FINAL_DATA/audits/anomaly_audit.csv",
            "保留49异常和未独立核验状态",
        ),
        (
            "warmup_checks",
            "07_VALIDATION_AND_TESTS/sanity_checks/warmup_checks.csv",
            "前样本Prior元数据核查",
        ),
        (
            "data_checks",
            "07_VALIDATION_AND_TESTS/sanity_checks/data_checks.csv",
            "日期/价格/日历/恒等式/缓存/信号核查",
        ),
        (
            "legacy_reconciliation",
            "07_VALIDATION_AND_TESTS/sanity_checks/legacy_reconciliation.csv",
            "675原终值逐行复现",
        ),
    ]:
        project_csv(
            src, rel, desc, "repair.data_audit.audit / repair.backtests.run_all"
        )
    keys = [
        "ticker",
        "night_rule",
        "day_rule",
        "strategy_id",
        "cost_bps",
        "model_version",
        "period_start",
        "period_end",
        "n",
    ]
    for cost in [0, 1, 2]:
        for sub, col in [
            ("terminal_wealth", "terminal_wealth"),
            ("mdd", "MDD"),
            ("volatility", "Vol"),
            ("sharpe", "SR"),
        ]:
            project_csv(
                "strategy_metrics_ledger",
                f"03_FINAL_RESULTS/{sub}/{sub}_{cost}bps_2007_2025.csv",
                "主结果指标；225 ETF/策略行",
                "repair.backtests.run_all",
                keys + [col],
                lambda r, c=cost: r["cost_bps"] == str(c),
                extra=(
                    (
                        lambda r: {
                            "metric_status": (
                                "undefined_zero_daily_variance"
                                if r["SR"] == ""
                                else "defined"
                            )
                        }
                    )
                    if col == "SR"
                    else None
                ),
            )
    trading = [
        "signal_transitions",
        "executed_trades",
        "rebalance_trades",
        "monetary_turnover",
        "equity_normalized_turnover",
        "transaction_cost",
        "borrow_cost",
        "financing_cost",
        "cash_interest",
        "distribution_cash",
        "terminal_receivable",
        "insolvent",
        "self_financing_error",
        "target_error",
    ]
    project_csv(
        "strategy_metrics_ledger",
        "03_FINAL_RESULTS/transaction_costs/transaction_costs_and_turnover_0_1_2bps_2007_2025.csv",
        "675组合实际成交、现金流、费用和残差",
        "repair.backtests.run_all",
        keys + trading,
    )
    project_csv(
        "strategy_metrics_ledger",
        "03_FINAL_RESULTS/other_final_results/annualized_growth_and_returns_0_1_2bps_2007_2025.csv",
        "CAGR及年化算术均值，区别于终值与Sharpe",
        "repair.backtests.run_all",
        keys + ["CAGR", "annualized_arithmetic_mean"],
    )
    project_csv(
        "cost_sensitivity",
        "03_FINAL_RESULTS/transaction_costs/cost_sensitivity_5_10bps_2007_2025.csv",
        "5/10bps补充情景；0/1/2不重复保存",
        "repair.backtests.run_all",
        keep=lambda r: r["cost_bps"] in ["5", "10"],
    )
    project_csv(
        "breakeven_costs",
        "03_FINAL_RESULTS/break_even_costs/break_even_costs_vs_buy_hold_and_cash_2007_2025.csv",
        "414根搜索结果，区分无毛优势和网格内无交叉",
        "repair.backtests.breakeven",
        rename={"cost_bps": "base_cost_bps"},
        extra={
            "cost_bps": "SEARCH_VARIABLE",
            "cost_definition": "breakeven_bps is the searched rate; base_cost_bps is gross-edge assessment point",
        },
    )
    project_csv(
        "subperiod_metrics",
        "03_FINAL_RESULTS/subperiod_results/subperiod_results.csv",
        "三个固定描述性时期的2025行完整指标",
        "repair.backtests.run_all",
    )
    project_csv(
        "financing_sensitivity",
        "03_FINAL_RESULTS/other_final_results/financing_and_distribution_settlement_scenarios.csv",
        "2025行现金/借券/融资/支付延迟敏感性",
        "repair.backtests.run_all",
    )
    project_csv(
        "outperformer_counts",
        "03_FINAL_RESULTS/other_final_results/outperformer_counts_by_model_and_cost.csv",
        "相对BH及绝对盈利汇总；active分母207",
        "repair.reporting.findings",
    )
    mapping = [
        (
            "session_tests",
            "session_mean_tests/session_mean_tests.csv",
            "27项无条件N/D/N-D均值检验",
        ),
        (
            "weekend_difference_tests",
            "session_mean_tests/weekend_holiday_difference_tests.csv",
            "完整时间序列直接周末/假日差异",
        ),
        (
            "subperiod_session_tests",
            "session_mean_tests/subperiod_session_mean_tests.csv",
            "固定三时期的81项session均值检验",
        ),
        (
            "reversal_decomposition",
            "predictability_tests/reversal_drift_covariance_decomposition.csv",
            "同有效样本反转均值/漂移/协方差分解及均值检验",
        ),
    ]
    for src, rel, desc in mapping:
        project_csv(
            src, "04_STATISTICAL_TESTS/" + rel, desc, "repair.inference.basic_tests"
        )
    project_csv(
        "predictability_tests",
        "04_STATISTICAL_TESTS/predictability_tests/same_session_predictability_tests.csv",
        "含截距AR1及新增符号诊断；72系数行",
        "repair.inference.basic_tests",
        keep=lambda r: r["session"] in ["N", "D"],
    )
    project_csv(
        "predictability_tests",
        "04_STATISTICAL_TESTS/predictability_tests/cross_session_predictability_diagnostics.csv",
        "独立跨session诊断；45系数行",
        "repair.inference.basic_tests",
        keep=lambda r: r["session"] == "cross_session",
    )
    project_csv(
        "pairwise_tests",
        "04_STATISTICAL_TESTS/bootstrap_tests/paired_stationary_bootstrap_tests.csv",
        "1863个最终策略/成本/block比较，含CI和MC误差",
        "repair.inference.pairwise",
        keep=lambda r: r["model_version"] == LEDGER,
    )
    project_csv(
        "spa_stepm_tests",
        "04_STATISTICAL_TESTS/SPA_StepM/spa_stepm_results.csv",
        "81个最终家庭检验，实际候选/种子/模拟精度",
        "repair.inference.spa_stepm",
        keep=lambda r: r["model_version"] == LEDGER,
        extra={
            "overnight_rule": "FAMILY_24_NON_BH",
            "daytime_rule": "FAMILY_24_NON_BH",
        },
    )
    project_csv(
        "model_comparison",
        "08_OLD_VS_NEW/old_vs_new_results.csv",
        "675行原/指数桥梁/现金账本及差异分解",
        "repair.backtests.run_all",
    )
    for src, rel, desc in [
        (
            "old_vs_new_pairwise_tests",
            "old_vs_new_bootstrap_tests.csv",
            "相同新协议/抽样下旧与新财富引擎；非旧论文原p值",
        ),
        (
            "old_vs_new_spa_stepm_tests",
            "old_vs_new_spa_stepm_tests.csv",
            "相同新协议/抽样下旧与新财富引擎；非旧论文原p值",
        ),
        (
            "original_protocol_reference_statistics",
            "original_protocol_reference_statistics.csv",
            "原analysis.py实际重跑统计；长格式保存原协议",
        ),
    ]:
        project_csv(
            src,
            "08_OLD_VS_NEW/" + rel,
            desc,
            "repair.reporting.findings / repair.legacy_provenance.collect",
            role="reference" if src.startswith("original") else "final",
        )
    for src in [
        "ledger_acceptance_checks",
        "original_table_reproduction",
        "retained_table_comparison",
    ]:
        copy(
            out / (src + ".csv"),
            "07_VALIDATION_AND_TESTS/validation_results/" + src + ".csv",
            "本次实际数值/源表验收证据",
            "pytest / source-to-table comparison",
        )
    for f in sorted((out / "latex_tables").glob("*.tex")):
        copy(
            f,
            "05_LATEX_TABLES/" + f.name,
            "从本次最终CSV生成的论文表格，Night/Day",
            "repair.presentation.tables",
        )
    for f in sorted((out / "figures").glob("*.png")):
        copy(
            f,
            "06_FIGURES/" + f.name,
            "从最终数值渲染、已视觉检查的研究图",
            "repair.presentation.figures",
        )
    lognames = [
        "dependency_install.log",
        "original_analysis.log",
        "original_tables.log",
        "original_figures.log",
        "repaired_backtests.log",
        "inference_and_bootstrap.log",
        "spa_stepm.log",
        "presentation.log",
        "final_figures.log",
        "findings.log",
        "portable_validation.log",
    ]
    for name in lognames:
        copy(
            project / "logs" / name,
            "07_VALIDATION_AND_TESTS/run_logs/" + name,
            "本次实际运行输出，不是恢复的旧日志",
            "actual rebuild command stdout/stderr",
        )
    copy(
        out / "execution_logs" / "pytest.log",
        "07_VALIDATION_AND_TESTS/run_logs/pytest.log",
        "完整最终pytest日志（含依赖弃用警告）",
        "run_reproduction.py --validate-only",
    )
    copy(
        out / "execution_logs" / "pytest_results.xml",
        "07_VALIDATION_AND_TESTS/validation_results/pytest_results.xml",
        "机器可读32测试逐项结果",
        "pytest --junitxml",
    )
    copy(
        out / "execution_logs" / "execution_manifest.json",
        "07_VALIDATION_AND_TESTS/validation_results/validation_execution_manifest.json",
        "最终验收命令真实起止/exit code",
        "run_reproduction.py --validate-only",
    )
    for f in (project / "provenance").glob("*.json"):
        copy(
            f,
            "09_REPORTS/provenance/" + f.name,
            "本次源与运行环境来源记录",
            "actual source extraction/runtime capture",
        )
    copy(
        out / "findings_summary.json",
        "09_REPORTS/findings_summary.json",
        "报告结论的单一机器可读汇总",
        "repair.reporting.findings",
    )
    copy(
        args.method_notes,
        "09_REPORTS/method_and_wording_notes.md",
        "方法公式与下一轮措辞建议；未写入论文",
        "retained method specification checked against rebuilt implementation",
        notes="Describes the unchanged repaired research definition; actual current run evidence is separate.",
    )

    suite = ET.parse(out / "execution_logs" / "pytest_results.xml").getroot()
    suites = suite.findall("testsuite") if suite.tag != "testsuite" else [suite]
    counts = {
        k: sum(int(x.get(a, 0)) for x in suites)
        for k, a in [
            ("total", "tests"),
            ("failed", "failures"),
            ("errors", "errors"),
            ("skipped", "skipped"),
        ]
    }
    counts["passed"] = (
        counts["total"] - counts["failed"] - counts["errors"] - counts["skipped"]
    )
    assert counts["failed"] == counts["errors"] == 0
    summary = json.loads((out / "findings_summary.json").read_text())
    write_documents(target, summary, counts)
    issue_rows = [
        dict(
            issue=a,
            verification_status=b,
            old_implementation=c,
            new_implementation=d,
            effect_on_results=e,
            paper_implication=f,
            evidence=g,
        )
        for a, b, c, d, e, f, g in ISSUES
    ]
    write_csv(target / "09_REPORTS/issue_verification_registry.csv", issue_rows)
    task_rows = [
        (
            "Stage 1",
            "COMPLETE",
            "675终值原代码复现；16原表byte match；原数据/代码不覆盖",
        ),
        (
            "Stage 2 internal checks",
            "COMPLETE",
            "4776共同样本、缓存/恒等式、首信号Prior元数据、行动及异常审计",
        ),
        (
            "Stage 2 independent vendor validation",
            "NOT TESTED",
            "独立来源与原下载时刻证据缺失，见U01/U02；未更换样本",
        ),
        (
            "Stage 3 ledger and execution accounting",
            "COMPLETE",
            "全部主场景与逐边界账本；17账本单元及全量验收",
        ),
        (
            "Stage 4 hypotheses and inference",
            "COMPLETE",
            "AR/sign/HAC/周末/多重检验/配对bootstrap/SPA/StepM实际运行",
        ),
        (
            "Stage 5 fixed robustness",
            "COMPLETE",
            "成本5/10bps、三时期、融资和20日分配场景",
        ),
        (
            "Stage 5 optional intraday/holdout",
            "NOT APPLICABLE",
            "未授权扩展新策略，真实分钟级数据缺失，未构造新holdout",
        ),
        (
            "Stage 6 machine-readable results and tables",
            "COMPLETE",
            "最终CSV/Parquet、24TeX、2PNG、差异报告/日志/清单",
        ),
        (
            "Stage 6 manuscript and literature rewriting",
            "DEFERRED BY USER",
            "正文未修改；按用户限制留待实证确认之后",
        ),
        (
            "Clean delivery",
            "COMPLETE",
            "只含筛选最终版本和明确reference；完整性检查在packaging_validation.json和ZIP校验记录",
        ),
    ]
    write_csv(
        target / "09_REPORTS/task_completion_status.csv",
        [dict(task=a, status=b, evidence_or_limit=c) for a, b, c in task_rows],
    )
    catalog = [
        dict(
            strategy_id=f"N_{n}__D_{d}",
            overnight_rule=n,
            daytime_rule=d,
            rule_order="NIGHT/DAY",
            night_signal=(
                "previous same-session frozen adjusted return"
                if n in ["Momentum", "Reversal"]
                else n
            ),
            day_signal=(
                "previous same-session frozen return"
                if d in ["Momentum", "Reversal"]
                else d
            ),
        )
        for n in ["Cash", "Long", "Short", "Momentum", "Reversal"]
        for d in ["Cash", "Long", "Short", "Momentum", "Reversal"]
    ]
    write_csv(target / "02_FINAL_DATA/strategy_catalog.csv", catalog)
    (target / "01_FINAL_CODE/run_instructions.md").write_text(
        """# Reproduction instructions

Use Python 3.13.5 (the tested runtime), a new virtual environment and the frozen input files. No data download is required. Run from 01_FINAL_CODE:

```sh
python3.13 -m venv /absolute/path/commodity-repro-venv
/absolute/path/commodity-repro-venv/bin/python -m pip install -r requirements.lock.txt
/absolute/path/commodity-repro-venv/bin/python run_reproduction.py --output /absolute/path/new-commodity-results
```

The output directory must be new or empty. The command executes the original pipeline, data audit, all ledger grids/sensitivities, inference, 24 tables, two figures, findings, then 32 tests. It writes real start/end times, exit codes and logs to execution_logs. Output figures/tables are generated from CSV/Parquet. Templates contain captions/headers/footnotes only, never numeric data rows. Static legacy table hashes provide an independent reproduction target.

To check an existing native output directory without re-estimating:

```sh
/absolute/path/commodity-repro-venv/bin/python run_reproduction.py --output /absolute/path/existing-native-results --validate-only
```

Defaults locate ../02_FINAL_DATA/provided_prices, ../08_OLD_VS_NEW/legacy_validation_inputs and ../07_VALIDATION_AND_TESTS/unit_tests. Override --input, --legacy-reference, --tests if needed. Source uses COMMODITY_INPUT_ROOT, COMMODITY_OUTPUT_ROOT and COMMODITY_LEGACY_REFERENCE_ROOT internally. The delivered categorized CSVs are lossless projections of native outputs; validation-only expects native outputs, not the delivery root.

Tests are stored once, under 07_VALIDATION_AND_TESTS/unit_tests. Numba runtime cache goes into the NEW results directory, not this delivery. No R/notebook/shell analysis was used; the actual scripts are Python. Original engine.py is unmodified and used for legacy reproduction and fixed rule definitions. requirements.txt pins direct scientific dependencies; requirements.lock.txt includes the tested transitive set. Platform-specific floating point may differ at the last bits; acceptance uses explicit numeric tolerances, not an arbitrary requirement that all CSV bytes match.

Root seed20260928; custom stationary bootstrap2000 draws; actual arch8.0.0 SPA/StepM5000 draws; expected block10 baseline and5/20 sensitivity. Exact integer sub-seeds are in every relevant CSV. No seed or specification search is performed. Original protocol statistics use its original global RNG sequence, so distinguish them from new-protocol inference applied to the legacy wealth model.

This rebuild was executed in isolated .venv_repro with actual logs. The CLI validation-only command was also executed from the delivered 01_FINAL_CODE, using delivered data and tests; all 32 passed. A second full end-to-end rerun of the newly assembled CLI was not performed merely to package results; stage execution and table provenance were verified separately. Lost historical logs are not recreated. Packaging uses build_delivery.py (requires the native rebuild project and its captured logs); it changes metadata/file layout only and never invokes analysis functions.

To audit this delivery's manifest, schemas, counts, aliases and absence of duplicate/cache files without running analysis, use the standard-library-only command from 01_FINAL_CODE:

```sh
python3 -B check_delivery.py --package ..
```
"""
    )
    (target / "05_LATEX_TABLES/README.md").write_text(
        """# Final table integration

All 24 tables are generated from current CSVs by repair.presentation.tables, using static caption/header/footnote templates without embedded numerical rows. They match the surviving prior repair tables byte for byte (retained_table_comparison.csv). Original legacy table results are not copied into this directory.

Use booktabs and adjustbox in the manuscript preamble; all tables use max width=\\linewidth. Include the desired file with \\input{...}. Labels preserve the revised table labels, so replace an old table rather than including both with duplicate labels. Table row strategy order is Night/Day. Main manuscript was not edited/compiled in this stage. Display rounding does not alter full precision CSVs.
"""
    )

    # Real stage evidence: exit status was observed by the orchestrating tool;
    # never invent absent start timestamps for earlier, uninstrumented commands.
    commands = {
        "original_analysis.log": "python -u analysis.py [unmodified original; legacy_execution/code]",
        "original_tables.log": "python make_tables.py [unmodified original]",
        "original_figures.log": "python make_figs.py [unmodified original]",
        "repaired_backtests.log": "from repair.data_audit import audit; from repair.backtests import run_all,breakeven; audit(); run_all(); breakeven()",
        "inference_and_bootstrap.log": "from repair.inference import basic_tests,pairwise; basic_tests(); pairwise()",
        "spa_stepm.log": "from repair.inference import spa_stepm; spa_stepm()",
        "presentation.log": "python -m repair.presentation",
        "final_figures.log": "from repair.presentation import figures; figures()",
        "findings.log": "python -m repair.reporting",
        "portable_validation.log": "python run_reproduction.py --output [native output absolute directory] --validate-only [executed from delivered 01_FINAL_CODE using delivered input data and tests]",
    }
    stages = [
        dict(
            log="07_VALIDATION_AND_TESTS/run_logs/" + name,
            command=cmd,
            exit_code=0,
            started_at_utc=None,
            log_last_modified_utc=dt.datetime.fromtimestamp(
                (project / "logs" / name).stat().st_mtime, dt.timezone.utc
            ).isoformat(),
            timing_note="Start timestamp was not instrumented; log mtime is not a claimed exact start/end time.",
            log_sha256=digest(project / "logs" / name),
        )
        for name, cmd in commands.items()
    ]
    manifest = dict(
        assembled_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        scope="new actual rebuild after user-deleted earlier full repair",
        runtime=json.loads(
            (project / "provenance" / "runtime_environment.json").read_text()
        ),
        source=json.loads(
            (project / "provenance" / "rebuild_source_manifest.json").read_text()
        ),
        stages=stages,
        final_test_counts=counts,
        earlier_historical_logs_recovered=False,
        manuscript_updated=False,
    )
    (target / "09_REPORTS/run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    write_csv(
        target / "07_VALIDATION_AND_TESTS/validation_results/copy_integrity_checks.csv",
        copy_checks,
    )
    write_csv(
        target / "07_VALIDATION_AND_TESTS/validation_results/csv_projection_checks.csv",
        projection_checks,
    )

    # Remove only the explicitly known incomplete delivery staging copies, never
    # anything in the original/rebuild workspace and never arbitrary target files.
    obsolete = [
        target / "00_README/copied_file_provenance.csv",
        target / "07_VALIDATION_AND_TESTS/validation_results/packaging_copy_checks.csv",
    ]
    prior_validation = target / "07_VALIDATION_AND_TESTS/run_logs/final_validation.log"
    if prior_validation.exists():
        assert digest(prior_validation) == digest(project / "logs/final_validation.log")
        obsolete.append(prior_validation)
    for t in TICKERS:
        f = target / "02_FINAL_DATA" / f"{t}_daily.csv"
        if f.exists():
            assert digest(f) == digest(
                target / "02_FINAL_DATA" / "provided_prices" / f.name
            )
            obsolete.append(f)
    for f in obsolete:
        if f.exists():
            f.unlink()
    for f in sorted(target.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(target).as_posix()
        if rel == "00_README/FILE_MANIFEST.csv":
            continue
        if rel not in records:
            register(
                rel,
                "本次交付说明、研究任务状态、校验或复现元数据",
                "build_delivery.py / repair.delivery_docs.write_documents",
            )
    for r in records.values():
        path = target / r["relative_path"]
        r["sha256"] = digest(path)
        r["size_bytes"] = path.stat().st_size
    records["00_README/FILE_MANIFEST.csv"] = dict(
        category="00_README",
        filename="FILE_MANIFEST.csv",
        relative_path="00_README/FILE_MANIFEST.csv",
        description="逐文件交付清单（自身不做循环hash）",
        generated_by="build_delivery.py",
        final_or_reference="final",
        notes="Self-reference: hash and size intentionally not computed for this row.",
        source_path="",
        sha256="SELF_REFERENCE",
        size_bytes="",
    )
    write_csv(
        target / "00_README/FILE_MANIFEST.csv",
        sorted(records.values(), key=lambda r: r["relative_path"]),
    )
    print(
        f"Curated {len(records)} files at {target}. Source files untouched.", flush=True
    )


if __name__ == "__main__":
    main()
