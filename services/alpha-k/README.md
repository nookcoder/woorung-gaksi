# Alpha-K: Multi-Agent Swing Trading System

> **5-Phase Pipeline** for Korean stock market swing trading using institutional-grade technical analysis, fundamental screening, and smart money flow detection.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Alpha-K Pipeline (LangGraph)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Phase 1: Market Filter ──────────────── MacroAgent             │
│  (ADR, V-KOSPI, FX Corr)   CRASH/BEAR → EXIT                  │
│         │                                                       │
│  Phase 2: Sector Screening ────────────── SectorAgent           │
│  (RS Score, Trickle-Down)   Top 3 Sectors → Candidate List     │
│         │                                                       │
│  Phase 3: Deep Dive (Parallel) ─────────┐                      │
│  ├─ 3A. Technical Sniper ─── OB/VCP/POC │                      │
│  ├─ 3B. Fundamental Valuator ── F-Score  │                      │
│  └─ 3C. Smart Money Agent ── 수급 분석   │                      │
│         │                                                       │
│  Phase 4: Scoring & Selection ──────────── Supervisor           │
│  (Tech*0.5 + Flow*0.3 + Fund*0.2)   Top 3 Stocks              │
│         │                                                       │
│  Phase 5: Trade Setup ─────────────────── RiskAgent             │
│  (ATR Stop, Pyramiding 30/30/40, R/R ≥ 2.0)                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Agents

| Agent                | Phase | Rule File                  | Key Logic                                               |
| -------------------- | ----- | -------------------------- | ------------------------------------------------------- |
| **MacroAgent**       | 1     | `01_market_regime.md`      | ADR 20d MA, V-KOSPI 급등 필터, USD/KRW 상관계수         |
| **SectorAgent**      | 2     | `02_sector_rotation.md`    | RS Score (1W/1M/3M Alpha), 낙수효과, 거래대금/60MA 필터 |
| **TechnicalAgent**   | 3A    | `03_technical_strategy.md` | Order Block (SMC), VCP 3-Phase, Volume Profile POC      |
| **FundamentalAgent** | 3B    | `04_fundamental.md`        | Piotroski F-Score ≥7, 섹터 상대 PER, DART 리스크        |
| **SmartMoneyAgent**  | 3C    | `05_smart_money.md`        | 프로그램 비차익, 외인/기관 우위, 5일 연속 매집          |
| **RiskAgent**        | 5     | `06_risk_management.md`    | Chandelier Stop (3×ATR), 피라미딩, R/R Pre-check        |

## Quick Start

```bash
cd services/alpha-k

# Install dependencies
pip install -r requirements.txt

# (Optional) OpenDART API Key for DART risk check
cp .env.example .env
# Edit .env and set OPENDART_API_KEY

# Full Pipeline (auto sector screening)
python src/main.py

# Analyze specific tickers (skip Phase 1 & 2)
python src/main.py --tickers 005930 000660 035420

# Custom account balance
python src/main.py --tickers 005930 --balance 50000000

# Save report to file
python src/main.py --output report.md
```

## Project Structure

```
services/alpha-k/
├── src/
│   ├── domain/
│   │   └── models.py           # Value Objects, Enums (all phases)
│   ├── infrastructure/
│   │   └── data_providers/
│   │       └── market_data.py  # FinanceDataReader + pykrx wrapper
│   ├── agents/
│   │   ├── macro_agent.py      # Phase 1: Market Regime
│   │   ├── sector_agent.py     # Phase 2: Sector Rotation
│   │   ├── technical_agent.py  # Phase 3A: SMC + VCP + POC
│   │   ├── fundamental_agent.py# Phase 3B: F-Score + PER + DART
│   │   ├── smart_money_agent.py# Phase 3C: 수급 분석
│   │   └── risk_agent.py       # Phase 5: Risk Management
│   ├── supervisor/
│   │   ├── state.py            # LangGraph State
│   │   └── graph.py            # 5-Phase Pipeline Graph
│   └── main.py                 # CLI Entry Point
├── requirements.txt
├── .env.example
└── README.md
```

## Non-Negotiable Rules

From `06_risk_management.md`:

1. **Position Sizing:** 30% → 30% → 40% pyramiding only
2. **Stop Loss:** `Entry - 3 × ATR(14)` — dynamic, not fixed %
3. **R/R ≥ 2.0:** No entry regardless of chart quality if R/R < 2.0
