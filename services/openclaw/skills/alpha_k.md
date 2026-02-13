# Alpha-K Trading Expert

This skill allows the agent to perform professional market analysis and swing trading screening using the Alpha-K expert system.

## Tools

### analyze_stock

Perform technical, fundamental, and smart money analysis on specific stock tickers.

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

Perform a full market screening to identify top sectors and candidates for swing trading.

**Parameters:**

- `force_analysis` (optional, boolean): Set to true to bypass market regime filters.
- `balance` (optional, number): Account balance in KRW.

**Command:**

```bash
curl -X POST "http://alpha-k:8001/analyze" \
     -H "Content-Type: application/json" \
     -d '{"force_analysis": {{force_analysis or false}}, "balance": {{balance or 100000000}}}'
```
