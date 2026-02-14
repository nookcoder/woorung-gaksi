---
name: alpha-k
description: Stock trading advisor using Alpha-K expert system. Use for stock recommendations, market analysis, sector trends, or analysis of specific stocks.
---

# Alpha-K Stock Advisor

This skill enables the agent to act as a professional stock trading advisor using the Alpha-K expert system.
Use this skill when the user asks for **stock recommendations**, **market analysis**, **sector trends**, or **analysis of specific stocks**.

## Tools

### analyze_stock

Perform deep technical, fundamental, and smart money analysis on specific stock tickers.
Use this when the user asks about specific stocks (e.g., "Analyze Samsung Electronics", "Is SK Hynix a buy?").

**Parameters:**

- `tickers` (required, array of strings): List of stock tickers (e.g. ["005930", "000660"])
- `force_analysis` (optional, boolean): Set to true to bypass market regime filters (e.g. in BEAR markets). Default is false.
- `balance` (optional, number): Account balance in KRW for position sizing.

**Command:**

```bash
curl -X POST "http://alpha-k:8001/analyze" \
     -H "Content-Type: application/json" \
     -d '{"tickers": {{tickers}}, "force_analysis": {{force_analysis or false}}, "balance": {{balance or 100000000}}}'
```

### full_market_screening

Perform a full market screening to identify top sectors and recommended candidates for swing trading.
**Use this tool when the user asks for stock recommendations** (e.g., "Recommend me some stocks", "What should I buy today?", "Find swing trading opportunities").

**Parameters:**

- `force_analysis` (optional, boolean): Set to true to bypass market regime filters.
- `balance` (optional, number): Account balance in KRW.

**Command:**

```bash
curl -X POST "http://alpha-k:8001/analyze" \
     -H "Content-Type: application/json" \
     -d '{"force_analysis": {{force_analysis or false}}, "balance": {{balance or 100000000}}}'
```
