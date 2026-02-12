---
description: 이 문서는 Supervisor Agent가 전체 트레이딩 프로세스를 오케스트레이션하는 순서를 정의한다.
---

# Workflow: Alpha-K Main Execution Pipeline

이 문서는 Supervisor Agent가 전체 트레이딩 프로세스를 오케스트레이션하는 순서를 정의한다.

## Phase 1: Market Filter (Go / No-Go)

1. **Supervisor** activates `Macro Quant Agent`.
2. **Macro Agent** checks `rules/01_market_regime.md`.
   - Calculate ADR, V-KOSPI, Exchange Rate Correlation.
3. **Decision:**
   - IF Market Status == "CRASH" or "BEAR": Terminate workflow. Report "Cash is King".
   - IF Market Status == "NORMAL" or "BULL": Proceed to Phase 2.

## Phase 2: Candidate Screening

1. **Supervisor** activates `Sector Rotation Agent`.
2. **Sector Agent** scans KOSPI/KOSDAQ sectors using `rules/02_sector_rotation.md`.
   - Identify Top 3 Sectors based on RS Score.
3. **Data Retrieval:** Fetch OHLCV data for stocks within Top 3 Sectors.
4. **Primary Filter:** Select stocks with Trading Value > 50B KRW (500억 원) & Above 60MA.
5. **Output:** List of Candidate Stocks (approx. 10~20).

## Phase 3: Deep Dive Analysis (Parallel Processing)

For each Candidate Stock, execute the following agents in parallel:

### A. Technical Analysis

- **Agent:** `Technical Sniper`
- **Rule:** `rules/03_technical_strategy.md`
- **Check:** Order Block support? VCP Pattern formed? Price > POC?
- **Output:** Technical Score (0-100) & Key Levels (Support/Resistance).

### B. Fundamental Analysis

- **Agent:** `Fundamental Valuator`
- **Rule:** `rules/04_fundamental.md`
- **Check:** Piotroski F-Score >= 7? Sector Relative PER < 0.8? DART Risks?
- **Output:** Fundamental Score (Pass/Fail).

### C. Flow Analysis

- **Agent:** `Smart Money Agent`
- **Rule:** `rules/05_smart_money.md`
- **Check:** Program Buying? Foreign Broker accumulation?
- **Output:** Flow Score (High/Medium/Low).

## Phase 4: Scoring & Final Selection

1. **Supervisor** aggregates results.
2. **Filtering Logic:**
   - Discard if Fundamental == Fail.
   - Discard if Technical Score < 70.
   - Discard if Flow Score == Low.
3. **Ranking:** Sort remaining stocks by (Technical Score _ 0.5 + Flow Score _ 0.3 + Fundamental Score \* 0.2).
4. **Selection:** Pick Top 3 Stocks.

## Phase 5: Trade Setup & Execution Plan

1. **Supervisor** activates `Risk Executioner`.
2. **Risk Agent** calculates for selected stocks using `rules/06_risk_management.md`:
   - Calculate ATR(14).
   - Set Stop Loss Price.
   - Calculate R/R Ratio.
   - Determine Position Sizing (Pyramiding plan).
3. **Final Output:** Generate a Markdown Report for Lucas.
   - **Structure:**
     - Ticker / Name
     - Buy Reason (Summary of Tech/Fund/Flow)
     - Entry Zone
     - Stop Loss (ATR Based)
     - Target Price
