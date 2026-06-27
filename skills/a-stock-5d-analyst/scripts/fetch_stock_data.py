#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_stock_data.py
A 股五维分析数据采集器。统一入口，多源降级，输出标准化 JSON。

用法:
  python fetch_stock_data.py --code 600519 --out /tmp/stock_600519.json
  python fetch_stock_data.py --resolve 茅台
  python fetch_stock_data.py --code 600519 --dims fundamental,technical
"""
import argparse
import json
import sys
import time
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

try:
    import akshare as ak
    import pandas as pd
except ImportError:
    print(json.dumps({"error": "missing dependency: pip install akshare pandas"}, ensure_ascii=False))
    sys.exit(1)


# ----------------- 工具：重试与降级 -----------------

def retry(fn, retries=3, delay=1.2, default=None):
    last_err = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            time.sleep(delay)
    return default


def df_to_records(df, max_rows=None):
    if df is None or len(df) == 0:
        return []
    if max_rows:
        df = df.tail(max_rows) if max_rows > 0 else df.head(-max_rows)
    return df.to_dict(orient="records")


def detect_market(code: str) -> str:
    """6 位代码 → sh / sz / bj"""
    if code.startswith(("60", "68", "11", "51")):
        return "sh"
    if code.startswith(("00", "30", "12", "15")):
        return "sz"
    if code.startswith(("8", "4")):
        return "bj"
    return "sh"


# ----------------- 解析名称 → 代码 -----------------

def resolve_name(name: str):
    """根据股票简称解析 6 位代码。"""
    candidates = []
    df = retry(lambda: ak.stock_info_a_code_name(), retries=2)
    if df is not None and len(df):
        hit = df[df["name"].str.contains(name, na=False)]
        for _, row in hit.head(5).iterrows():
            candidates.append({"code": row["code"], "name": row["name"]})
    return candidates


# ----------------- 基本面 -----------------

def fetch_fundamental(code: str) -> dict:
    out = {"errors": []}

    # 个股基础信息：优先新浪 spot，降级东财
    info_src = retry(lambda: ak.stock_individual_basic_info_xq(symbol=f"{detect_market(code).upper()}{code}"), retries=2)
    if info_src is not None and len(info_src):
        out["info"] = {row["item"]: str(row["value"]) for _, row in info_src.iterrows()}
    else:
        info_em = retry(lambda: ak.stock_individual_info_em(symbol=code), retries=2)
        if info_em is not None and len(info_em):
            out["info"] = {row["item"]: str(row["value"]) for _, row in info_em.iterrows()}
        else:
            out["errors"].append("individual_info failed (both xq & em)")

    # 财务摘要（多期）
    abstract = retry(lambda: ak.stock_financial_abstract(symbol=code), retries=3)
    if abstract is not None and len(abstract):
        # 只保留最近 8 期
        period_cols = [c for c in abstract.columns if c not in ("选项", "指标")]
        period_cols = sorted(period_cols, reverse=True)[:8]
        keep_cols = ["选项", "指标"] + period_cols
        out["financial_abstract"] = df_to_records(abstract[keep_cols])
    else:
        out["errors"].append("financial_abstract failed")

    # 关键财务指标按年
    indicator = retry(lambda: ak.stock_financial_analysis_indicator(symbol=code, start_year="2020"), retries=2)
    if indicator is not None and len(indicator):
        out["financial_indicator"] = df_to_records(indicator, max_rows=20)
    else:
        out["errors"].append("financial_analysis_indicator failed")

    # 估值（PE PB PS 历史分位 - 用近 5 年东财数据）
    val = retry(lambda: ak.stock_a_indicator_lg(symbol=code), retries=2)
    if val is not None and len(val):
        val = val.sort_values("trade_date").tail(1300)  # 约 5 年
        latest = val.iloc[-1].to_dict()
        out["valuation_latest"] = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in latest.items()}
        # 分位
        def quantile(col):
            if col not in val.columns: return None
            s = val[col].dropna()
            if len(s) < 50: return None
            cur = s.iloc[-1]
            return {
                "current": float(cur),
                "pct_5y": float((s <= cur).sum() / len(s)),
                "min_5y": float(s.min()),
                "max_5y": float(s.max()),
                "median_5y": float(s.median()),
            }
        out["valuation_quantile"] = {
            "pe_ttm": quantile("pe_ttm"),
            "pb": quantile("pb"),
            "ps_ttm": quantile("ps_ttm"),
            "dv_ratio": quantile("dv_ratio"),
        }
    else:
        out["errors"].append("indicator_lg failed")

    return out


# ----------------- 技术面 -----------------

def fetch_technical(code: str) -> dict:
    out = {"errors": []}
    market = detect_market(code)
    end = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y%m%d")

    # 日 K（优先新浪 - 更稳定）
    daily = retry(
        lambda: ak.stock_zh_a_daily(symbol=f"{market}{code}", start_date=start, end_date=end, adjust="qfq"),
        retries=3,
    )
    if daily is None or len(daily) == 0:
        # 降级东财
        daily = retry(
            lambda: ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq"),
            retries=3,
        )
        if daily is not None and len(daily):
            daily = daily.rename(columns={"日期": "date", "开盘": "open", "收盘": "close",
                                          "最高": "high", "最低": "low", "成交量": "volume"})

    if daily is None or len(daily) == 0:
        out["errors"].append("daily kline failed (both sina & em)")
        return out

    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"]).dt.strftime("%Y-%m-%d")
    daily = daily.sort_values("date").reset_index(drop=True)

    # 计算均线与 MACD
    closes = daily["close"].astype(float)
    for n in (5, 20, 60, 120, 250):
        daily[f"ma{n}"] = closes.rolling(n).mean().round(3)

    ema12 = closes.ewm(span=12, adjust=False).mean()
    ema26 = closes.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    macd = (dif - dea) * 2
    daily["dif"] = dif.round(4)
    daily["dea"] = dea.round(4)
    daily["macd"] = macd.round(4)

    # 输出最近 60 个交易日
    recent = daily.tail(60).round(3)
    out["daily_recent_60"] = df_to_records(recent)

    # 周线、月线（重采样）
    daily["dt"] = pd.to_datetime(daily["date"])
    weekly = daily.set_index("dt").resample("W").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum"
    }).dropna()
    weekly["ma60"] = weekly["close"].rolling(60).mean().round(3)
    out["weekly_recent_30"] = [
        {"date": idx.strftime("%Y-%m-%d"), **{k: (round(v, 3) if pd.notna(v) else None) for k, v in row.items()}}
        for idx, row in weekly.tail(30).iterrows()
    ]

    monthly = daily.set_index("dt").resample("ME").agg({
        "open": "first", "high": "max", "low": "min", "close": "last",
        "volume": "sum"
    }).dropna()
    monthly["ma20"] = monthly["close"].rolling(20).mean().round(3)
    out["monthly_recent_24"] = [
        {"date": idx.strftime("%Y-%m-%d"), **{k: (round(v, 3) if pd.notna(v) else None) for k, v in row.items()}}
        for idx, row in monthly.tail(24).iterrows()
    ]

    # 关键信号摘要
    last = daily.iloc[-1]
    prev = daily.iloc[-2] if len(daily) > 1 else last
    signals = {
        "latest_close": float(last["close"]),
        "latest_date": last["date"],
        "ma5": float(last["ma5"]) if pd.notna(last["ma5"]) else None,
        "ma20": float(last["ma20"]) if pd.notna(last["ma20"]) else None,
        "ma60": float(last["ma60"]) if pd.notna(last["ma60"]) else None,
        "ma120": float(last["ma120"]) if pd.notna(last["ma120"]) else None,
        "ma250": float(last["ma250"]) if pd.notna(last["ma250"]) else None,
        "above_ma20": bool(last["close"] > last["ma20"]) if pd.notna(last["ma20"]) else None,
        "above_ma60": bool(last["close"] > last["ma60"]) if pd.notna(last["ma60"]) else None,
        "above_ma250": bool(last["close"] > last["ma250"]) if pd.notna(last["ma250"]) else None,
        "macd_dif": float(last["dif"]),
        "macd_dea": float(last["dea"]),
        "macd_hist": float(last["macd"]),
        "macd_golden_cross": bool(prev["dif"] < prev["dea"] and last["dif"] > last["dea"]),
        "macd_above_zero": bool(last["dif"] > 0 and last["dea"] > 0),
    }
    if len(monthly) >= 2:
        m_last = monthly.iloc[-1]
        signals["monthly_above_ma20"] = bool(m_last["close"] > m_last["ma20"]) if pd.notna(m_last.get("ma20")) else None
    if len(weekly) >= 2:
        w_last = weekly.iloc[-1]
        signals["weekly_above_ma60"] = bool(w_last["close"] > w_last["ma60"]) if pd.notna(w_last.get("ma60")) else None
    out["signals"] = signals

    return out


# ----------------- 资金面 -----------------

def fetch_capital(code: str) -> dict:
    out = {"errors": []}
    market = detect_market(code)

    # 个股资金流（东财）—— 失败则降级到同花顺的资金流接口
    flow = retry(lambda: ak.stock_individual_fund_flow(stock=code, market=market), retries=3)
    if flow is None or len(flow) == 0:
        flow = retry(lambda: ak.stock_fund_flow_individual(symbol="即时"), retries=1)
        if flow is not None and len(flow):
            sub = flow[flow["股票代码"].astype(str) == code] if "股票代码" in flow.columns else None
            if sub is not None and len(sub):
                out["fund_flow_snapshot"] = df_to_records(sub.head(5))
            else:
                out["errors"].append("individual_fund_flow failed (both em & ths)")
        else:
            out["errors"].append("individual_fund_flow failed")
    else:
        out["fund_flow_recent_20"] = df_to_records(flow.tail(20))

    # 北向资金持股（多源降级：东财 individual → 东财 individual_detail → 东财 hold_stock 快照）
    hsgt = retry(lambda: ak.stock_hsgt_individual_em(symbol=code), retries=2)
    hsgt_source = "stock_hsgt_individual_em"
    if hsgt is None or len(hsgt) == 0:
        end_dt = datetime.now().strftime("%Y%m%d")
        start_dt = (datetime.now() - timedelta(days=40)).strftime("%Y%m%d")
        # 兜底 1：用 individual_detail_em（按代码 + 日期区间）
        hsgt = retry(
            lambda: ak.stock_hsgt_individual_detail_em(symbol=code, start_date=start_dt, end_date=end_dt),
            retries=2,
        )
        if hsgt is not None and len(hsgt):
            hsgt_source = "stock_hsgt_individual_detail_em"
    if hsgt is None or len(hsgt) == 0:
        # 兜底 2：从 hold_stock_em（沪深港通持股汇总，按市场+日期）里筛代码
        hsgt_agg = retry(
            lambda: ak.stock_hsgt_hold_stock_em(market="北向", indicator="今日排行"),
            retries=2,
        )
        if hsgt_agg is not None and len(hsgt_agg):
            code_col = next((c for c in ("代码", "股票代码") if c in hsgt_agg.columns), None)
            if code_col is not None:
                sub = hsgt_agg[hsgt_agg[code_col].astype(str) == code]
                if len(sub):
                    hsgt = sub
                    hsgt_source = "stock_hsgt_hold_stock_em(snapshot)"

    if hsgt is not None and len(hsgt):
        out["northbound_recent_20"] = df_to_records(hsgt.tail(20))
        out["northbound_source"] = hsgt_source
    else:
        out["errors"].append("northbound fetch failed (individual_em / individual_detail_em / hold_stock_em all failed)")

    # 龙虎榜（近 90 日）
    today = datetime.now().strftime("%Y%m%d")
    start = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
    all_lhb = retry(lambda: ak.stock_lhb_detail_em(start_date=start, end_date=today), retries=2)
    if all_lhb is not None and len(all_lhb):
        sub = all_lhb[all_lhb["代码"].astype(str) == code]
        out["lhb_recent"] = df_to_records(sub.head(20))
        if len(sub) == 0:
            out["lhb_note"] = "近 90 日未上龙虎榜"
    else:
        out["errors"].append("lhb fetch failed")

    return out


# ----------------- 预期面 -----------------

def fetch_expectation(code: str) -> dict:
    out = {"errors": []}

    # 主营业务构成（确认业务质量）
    main = retry(lambda: ak.stock_zygc_em(symbol=f"{detect_market(code).upper()}{code}"), retries=2)
    if main is not None and len(main):
        out["main_business"] = df_to_records(main.head(20))

    # 业绩预告
    forecast = retry(lambda: ak.stock_yjbb_em(date=datetime.now().strftime("%Y%m%d")[:6] + "30"), retries=1)
    if forecast is not None and len(forecast):
        sub = forecast[forecast["股票代码"] == code]
        if len(sub):
            out["yjbb"] = df_to_records(sub.head(5))

    # 研究报告（近 30 天）
    research = retry(lambda: ak.stock_research_report_em(symbol=code), retries=2)
    if research is not None and len(research):
        out["research_reports"] = df_to_records(research.head(20))
    else:
        out["errors"].append("research_report fetch failed")

    # 机构评级
    rating = retry(lambda: ak.stock_institute_recommend_detail(symbol=code), retries=1)
    if rating is not None and len(rating):
        out["institute_rating"] = df_to_records(rating.head(20))

    return out


# ----------------- 新闻情绪面 -----------------

def fetch_news(code: str) -> dict:
    out = {"errors": []}

    # 个股新闻
    news = retry(lambda: ak.stock_news_em(symbol=code), retries=3)
    if news is not None and len(news):
        out["company_news"] = df_to_records(news.head(20))
    else:
        out["errors"].append("stock_news_em failed")

    # 公司公告
    notice = retry(lambda: ak.stock_notice_report(symbol="全部", date=datetime.now().strftime("%Y%m%d")), retries=1)
    if notice is not None and len(notice):
        sub = notice[notice["代码"].astype(str) == code] if "代码" in notice.columns else None
        if sub is not None and len(sub):
            out["notice"] = df_to_records(sub.head(10))

    return out


# ----------------- 主入口 -----------------

DIMENSIONS = {
    "fundamental": fetch_fundamental,
    "technical": fetch_technical,
    "capital": fetch_capital,
    "expectation": fetch_expectation,
    "news": fetch_news,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", help="6 位 A 股代码")
    parser.add_argument("--resolve", help="按简称解析代码")
    parser.add_argument("--out", help="输出 JSON 路径，默认 stdout")
    parser.add_argument("--dims", default="all",
                        help="逗号分隔的维度: fundamental,technical,capital,expectation,news 或 all")
    args = parser.parse_args()

    if args.resolve:
        cands = resolve_name(args.resolve)
        result = {"query": args.resolve, "candidates": cands}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if not args.code:
        print("ERROR: --code or --resolve required", file=sys.stderr)
        sys.exit(2)

    code = args.code.strip()
    if len(code) != 6 or not code.isdigit():
        print(f"ERROR: invalid code '{code}'", file=sys.stderr)
        sys.exit(2)

    dims = list(DIMENSIONS.keys()) if args.dims == "all" else [d.strip() for d in args.dims.split(",")]

    result = {
        "code": code,
        "market": detect_market(code),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "dimensions": {},
    }

    for d in dims:
        if d not in DIMENSIONS:
            continue
        print(f"[fetching {d}...]", file=sys.stderr)
        try:
            result["dimensions"][d] = DIMENSIONS[d](code)
        except Exception as e:
            result["dimensions"][d] = {"errors": [f"top-level exception: {e}"]}

    out_json = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_json)
        print(f"[saved to {args.out}]", file=sys.stderr)
    else:
        print(out_json)


if __name__ == "__main__":
    main()
