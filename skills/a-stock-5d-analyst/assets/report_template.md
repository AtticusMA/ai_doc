# {{stock_name}}（{{stock_code}}）五维分析报告

> 数据时点：{{data_date}} | 生成时间：{{generated_at}} | 持有周期：{{horizon}}

## 一句话结论

**{{one_line_conclusion}}**

- **共振强度**：{{resonance_level}}（命中"{{resonance_rule}}"）
- **建议动作**：{{action}}
- **建议仓位**：{{position}}

---

## 一、基本面

### 公司概况
- 行业：{{industry}}
- 主营：{{main_business}}
- 总市值 / 流通市值：{{mkt_cap}} / {{free_mkt_cap}}

### 财务关键指标（近 3-5 期）

| 指标 | {{p1}} | {{p2}} | {{p3}} | {{p4}} | 趋势 |
|------|--------|--------|--------|--------|------|
| 营收（亿元） | | | | | |
| 营收增速 | | | | | |
| 归母净利（亿元） | | | | | |
| 净利增速 | | | | | |
| 毛利率 | | | | | |
| ROE | | | | | |
| 经营现金流/净利 | | | | | |
| 资产负债率 | | | | | |

### 估值

| 指标 | 当前值 | 5 年分位 | 5 年中位数 | 解读 |
|------|--------|----------|------------|------|
| PE_TTM | | | | |
| PB | | | | |
| PS_TTM | | | | |
| 股息率 | | | | |

### 基本面信号：**{{fund_signal}}**
依据：
1. {{fund_evidence_1}}
2. {{fund_evidence_2}}

---

## 二、技术面

### 多周期趋势

| 周期 | 收盘 | 关键均线 | 是否站上 | 信号 |
|------|------|----------|----------|------|
| 月线 | | 20MA = | | |
| 周线 | | 60MA = | | |
| 日线 | | 250MA = | | |

### 关键指标
- MACD（日线）：DIF={{dif}}, DEA={{dea}}, 柱={{hist}}, 是否零轴上方：{{macd_above_zero}}
- 量价：{{volume_price_summary}}
- 关键支撑 / 压力位：{{support}} / {{resistance}}

### 技术面信号：**{{tech_signal}}**
依据：
1. {{tech_evidence_1}}
2. {{tech_evidence_2}}

---

## 三、资金面

### 近 20 日资金流

| 类型 | 近 5 日 | 近 20 日 | 趋势 |
|------|---------|----------|------|
| 主力净流入 | | | |
| 北向资金持股变动 | | | |
| 融资余额变化 | | | |

### 龙虎榜（近 90 日）
{{lhb_summary}}

### 资金面信号：**{{capital_signal}}**
依据：
1. {{capital_evidence_1}}
2. {{capital_evidence_2}}

---

## 四、预期面

### 一致预期 vs 实际
- 最新季报：{{latest_report}}
- 一致预期：{{consensus}}
- 实际 vs 预期：{{vs_consensus}}

### 催化剂
{{catalyst_list}}

### 预期面信号：**{{expectation_signal}}**
依据：
1. {{expectation_evidence_1}}
2. {{expectation_evidence_2}}

---

## 五、新闻情绪面

### 近期重要公告 / 新闻（仅决策级信源）
{{news_list}}

### 研报评级变化
{{rating_change}}

### 新闻面信号：**{{news_signal}}**
依据：
1. {{news_evidence_1}}
2. {{news_evidence_2}}

---

## 六、共振判定矩阵

| 维度 | 信号 | 核心依据 |
|------|------|----------|
| 基本面 | {{fund_signal}} | {{fund_evidence_1}} |
| 技术面 | {{tech_signal}} | {{tech_evidence_1}} |
| 资金面 | {{capital_signal}} | {{capital_evidence_1}} |
| 预期面 | {{expectation_signal}} | {{expectation_evidence_1}} |
| 新闻面 | {{news_signal}} | {{news_evidence_1}} |

**共振强度**：{{resonance_level}}
**最终决策**：{{action}}

---

## 七、仓位与执行建议

- **建议仓位**：{{position}}
- **分批节奏**：{{batch_plan}}
- **止损线**：{{stop_loss}}
- **目标位**：{{target}}

---

## 八、逻辑反转触发条件（动态跟踪用）

出现以下任一信号即重新审视；多个同时出现立即清仓：

1. **基本面反转**：{{rev_fundamental}}
2. **技术面破位**：{{rev_technical}}
3. **资金面撤离**：{{rev_capital}}

---

## 九、数据来源声明

- AkShare（新浪 / 东财 / 同花顺等公开接口）
- 必要时通过 WebFetch 复核巨潮、交易所、券商研报
- 已知数据缺失：{{data_gaps}}

---

## 风险提示

本报告基于公开数据整理而成，不构成任何投资建议。股市有风险，投资需谨慎。所有分析结论的落地效果，与投资者的执行能力、风险适配程度高度相关，不存在无风险的投资策略。
