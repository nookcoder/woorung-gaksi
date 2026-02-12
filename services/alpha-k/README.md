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

## Data Sources

| 데이터                  | 소스                | 라이브러리/API                   |
| ----------------------- | ------------------- | -------------------------------- |
| OHLCV (일봉)            | Yahoo Finance / KRX | FinanceDataReader                |
| KOSPI/KOSDAQ 지수       | Yahoo Finance       | FinanceDataReader                |
| USD/KRW 환율            | Yahoo Finance       | FinanceDataReader                |
| ADR (상승/하락 종목 수) | KRX                 | FinanceDataReader `StockListing` |
| V-KOSPI 200             | KRX                 | FinanceDataReader                |
| **투자자별 매매동향**   | **KRX**             | **KIS Open API** `FHKST01010900` |
| **업종 시세**           | **KRX**             | **KIS Open API** `FHKUP03500100` |
| **PER/PBR/EPS/시총**    | **KRX**             | **KIS Open API** `FHKST01010100` |
| **프로그램 매매**       | **KRX**             | **KIS Open API** `FHKST01010200` |
| 공시 리스크             | DART                | OpenDART API (선택)              |

## Agents

| Agent                | Phase | Rule File                  | Key Logic                                               |
| -------------------- | ----- | -------------------------- | ------------------------------------------------------- |
| **MacroAgent**       | 1     | `01_market_regime.md`      | ADR, V-KOSPI 급등 필터, USD/KRW 상관계수                |
| **SectorAgent**      | 2     | `02_sector_rotation.md`    | RS Score (1W/1M/3M Alpha), 낙수효과, 거래대금/60MA 필터 |
| **TechnicalAgent**   | 3A    | `03_technical_strategy.md` | Order Block (SMC), VCP 3-Phase, Volume Profile POC      |
| **FundamentalAgent** | 3B    | `04_fundamental.md`        | Piotroski F-Score ≥7, 섹터 상대 PER, DART 리스크        |
| **SmartMoneyAgent**  | 3C    | `05_smart_money.md`        | 프로그램 비차익, 외인/기관 우위, 5일 연속 매집          |
| **RiskAgent**        | 5     | `06_risk_management.md`    | Chandelier Stop (3×ATR), 피라미딩, R/R Pre-check        |

## Prerequisites

### KIS Open API Key (필수)

투자자 수급, 업종 시세, PER/PBR 등 핵심 데이터를 제공합니다.

1. [한국투자증권 계좌 개설](https://www.koreainvestment.com)
2. [KIS Developers](https://apiportal.koreainvestment.com) → 앱 등록 → App Key / App Secret 발급
3. `.env` 파일에 설정

```bash
KIS_APP_KEY=your_app_key
KIS_APP_SECRET=your_app_secret
KIS_ACCOUNT_NO=12345678-01
```

> 모의투자 계좌도 사용 가능합니다.

### DART API Key (선택)

FundamentalAgent의 DART 공시 리스크 체크에 사용됩니다.

## Quick Start

```bash
cd services/alpha-k

# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure API keys
cp .env.example .env
# Edit .env: KIS_APP_KEY, KIS_APP_SECRET 설정

# 3. Full Pipeline (auto sector screening)
python src/main.py

# 4. Analyze specific tickers (skip Phase 1 & 2)
python src/main.py --tickers 005930 000660 035420

# 5. Custom account balance
python src/main.py --tickers 005930 --balance 50000000

# 6. Save report to file
python src/main.py --output report.md
```

## Project Structure

```
services/alpha-k/
├── src/
│   ├── domain/
│   │   └── models.py               # Value Objects, Enums (all phases)
│   ├── infrastructure/
│   │   └── data_providers/
│   │       ├── kis_client.py        # KIS Open API REST 클라이언트
│   │       └── market_data.py       # KIS + FDR 통합 데이터 제공자
│   ├── agents/
│   │   ├── macro_agent.py           # Phase 1: Market Regime
│   │   ├── sector_agent.py          # Phase 2: Sector Rotation
│   │   ├── technical_agent.py       # Phase 3A: SMC + VCP + POC
│   │   ├── fundamental_agent.py     # Phase 3B: F-Score + PER + DART
│   │   ├── smart_money_agent.py     # Phase 3C: 수급 분석
│   │   └── risk_agent.py            # Phase 5: Risk Management
│   ├── supervisor/
│   │   ├── state.py                 # LangGraph State
│   │   └── graph.py                 # 5-Phase Pipeline Graph
│   └── main.py                      # CLI Entry Point
├── requirements.txt
├── .env.example
└── README.md
```

## KIS API Endpoints Used

| tr_id           | 기능              | 용도                         |
| --------------- | ----------------- | ---------------------------- |
| `FHKST01010100` | 주식현재가 시세   | PER, PBR, 시총, 거래대금     |
| `FHKST01010900` | 주식현재가 투자자 | 외인/기관/개인 순매수 (30일) |
| `FHKST01010200` | 주식현재가 회원사 | 프로그램 매매 (비차익/차익)  |
| `FHKST03010100` | 기간별 시세       | 종목 일봉 OHLCV              |
| `FHKUP03500100` | 업종 기간별 시세  | 섹터 지수 OHLCV              |
| `FHPUP02100000` | 업종 현재 지수    | 섹터 현재가                  |

## Non-Negotiable Rules

From `06_risk_management.md`:

1. **Position Sizing:** 30% → 30% → 40% pyramiding only
2. **Stop Loss:** `Entry - 3 × ATR(14)` — dynamic, not fixed %
3. **R/R ≥ 2.0:** No entry regardless of chart quality if R/R < 2.0
