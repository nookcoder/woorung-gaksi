---
trigger: model_decision
description: "Alpha-K 프로젝트 요구사항 명세서"를 바탕으로 구현해달라고 부탁할 때 참고해야함
---

# Rule: Macro & Market Regime Analysis

이 규칙은 시장 진입 여부(Market Timing)와 자금 투입 비중(Bet Sizing)을 결정하는 최상위 로직이다.

## 1. ADR (Advance-Decline Ratio) Market Breadth

시장 너비 지표를 사용하여 과매도/과매수 구간을 판단한다.

- **Formula:** 20-Day Moving Average of (Daily Advancing Issues / Daily Declining Issues)
- **Thresholds:**
  - `ADR < 75`: Panic/Oversold (Aggressive Buy Signal). Bet Size = 100%.
  - `75 <= ADR <= 120`: Normal Market. Bet Size = Based on Setup Quality.
  - `ADR > 120`: Overbought (Euphoria). Reduce Positions. Bet Size = 0% or Short only.

## 2. V-KOSPI (Volatility Filter)

변동성 지수를 통해 폭락장을 회피한다.

- **Data:** KOSPI 200 Volatility Index (V-KOSPI)
- **Condition:**
  - IF (Current V-KOSPI > Previous V-KOSPI \* 1.05) AND (KOSPI Index < 20MA):
    - **Action:** HARD STOP (No New Entry).

## 3. Exchange Rate Correlation

환율과 주가의 역상관 관계가 깨진 비정상 시장을 필터링한다.

- **Data:** USD/KRW, KOSPI Index
- **Metric:** 20-Day Pearson Correlation Coefficient.
- **Condition:**
  - IF Correlation > 0.2 (Positive Correlation): Market is decoupling. Reduce Bet Size by 50%.

## Implementation Notes

- **ADR:** FinanceDataReader `StockListing('KOSPI')` → 당일 전 종목 등락률 스냅샷 기반 계산.
- **V-KOSPI:** FinanceDataReader `DataReader('VKOSPI')` → KOSPI 200 변동성 지수.
- **환율:** FinanceDataReader `DataReader('USD/KRW')` → USD/KRW 환율.
- **KOSPI Index:** FinanceDataReader `DataReader('KS11')` → KOSPI 지수 종가.
