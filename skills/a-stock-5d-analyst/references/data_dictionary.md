# fetch_stock_data.py 输出 JSON 字段字典

脚本输出的 JSON 顶层结构：

```json
{
  "code": "600519",
  "market": "sh",
  "generated_at": "ISO8601 时间戳",
  "dimensions": {
    "fundamental": { ... },
    "technical": { ... },
    "capital": { ... },
    "expectation": { ... },
    "news": { ... }
  }
}
```

每个维度内若有 `errors` 数组，需注意可能部分接口拉取失败，分析时优先用其他可用字段。

## fundamental（基本面）

| 字段 | 含义 |
|------|------|
| `info` | 个股基础信息字典：股票简称、行业、总股本、流通股、市值、流通市值等 |
| `financial_abstract` | 财务摘要多期，含营业收入、净利润、ROE、毛利率、负债率等，每行一个指标多列对应不同报告期 |
| `financial_indicator` | 财务分析指标按年，扣非净利、EPS、每股净资产、经营现金流/股等 |
| `valuation_latest` | 当前最新一日的 PE_TTM、PB、PS_TTM、股息率 |
| `valuation_quantile` | 近 5 年估值的当前值、分位（0-1）、最大、最小、中位数 |

## technical（技术面）

| 字段 | 含义 |
|------|------|
| `daily_recent_60` | 近 60 个交易日日 K，含 OHLCV 和 MA5/20/60/120/250、DIF/DEA/MACD |
| `weekly_recent_30` | 近 30 周的周 K，含 MA60 |
| `monthly_recent_24` | 近 24 月的月 K，含 MA20 |
| `signals` | 关键技术信号汇总（见下） |

`signals` 内字段：

| 字段 | 含义 |
|------|------|
| `latest_close` / `latest_date` | 最新收盘价与日期 |
| `ma5/20/60/120/250` | 对应日均线值 |
| `above_ma20/60/250` | 当前价是否在该均线上方 |
| `macd_dif/dea/hist` | MACD 三值 |
| `macd_golden_cross` | 是否刚发生金叉（DIF 上穿 DEA） |
| `macd_above_zero` | DIF、DEA 是否都在零轴上方 |
| `monthly_above_ma20` | 月线是否站上 20 月均线（最关键长期信号） |
| `weekly_above_ma60` | 周线是否站上 60 周均线（中期分界） |

## capital（资金面）

| 字段 | 含义 |
|------|------|
| `fund_flow_recent_20` | 近 20 日个股资金流入流出，含主力净流入、超大单、大单、中单、小单 |
| `northbound_recent_20` | 近 20 日北向资金持股变动 |
| `lhb_recent` | 近 90 日龙虎榜上榜记录 |
| `lhb_note` | 若无上榜，标注"近 90 日未上龙虎榜" |

## expectation（预期面）

| 字段 | 含义 |
|------|------|
| `main_business` | 主营业务构成与占比 |
| `yjbb` | 业绩预告（如适用） |
| `research_reports` | 近期研报：标题、机构、评级、目标价 |
| `institute_rating` | 机构评级明细 |

## news（新闻情绪面）

| 字段 | 含义 |
|------|------|
| `company_news` | 个股新闻列表：标题、内容、发布时间、来源 |
| `notice` | 公司公告（如当日有） |

## 字段缺失的容错原则

- 如 fundamental.info 缺失，分析报告"公司概况"段直接标注"基础信息未取到，已用 financial_abstract 中的指标推断"
- 如 valuation_quantile 缺失，估值章节用同行业可比估值替代（需 WebSearch 补充）
- 如 northbound_recent_20 缺失，资金面只看 fund_flow 和 lhb，明确告知用户"北向数据本次未取到"
- **绝不**因为某字段缺失就编造数据。明确说"该项数据未取到"。
