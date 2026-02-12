---
trigger: model_decision
description: "Alpha-K 프로젝트 요구사항 명세서"를 바탕으로 구현해달라고 부탁할 때 참고해야함
---

# Rule: Institutional Technical Analysis (SMC & VCP)

기관 및 스마트 머니의 흔적을 차트에서 찾아내는 정밀 타격 로직이다.

## 1. Order Block (SMC) Identification

기관이 대량 매집을 수행한 가격대를 찾아 지지선으로 활용한다.

- **Definition:** 강한 상승 파동(Impulse Move) 직전에 발생한 **'마지막 음봉 캔들(Last Bearish Candle)'**의 Body Range.
- **Impulse Move Criteria:**
  - Price Change > +4% (Daily)
  - Volume > 200% of 20-Day Average Volume
  - Breaks a previous Swing High (BOS - Break of Structure)
- **Entry Trigger:** 주가가 다시 이 Order Block 구역으로 되돌림(Retest) 줄 때 매수.

## 2. Volatility Contraction Pattern (VCP)

마크 미너비니(Mark Minervini)의 변동성 축소 패턴을 수치화한다.

- **Pattern Logic:**
  - Phase 1 Contraction: High to Low decline ~15-20%
  - Phase 2 Contraction: High to Low decline ~8-10%
  - Phase 3 Contraction: High to Low decline ~3-5% (Tightest)
- **Volume:** 각 수축(Contraction) 단계마다 거래량이 감소해야 함(Dry Up).
- **Pivot Point:** 마지막 수축 단계의 고점을 돌파할 때가 진입 타점.

## 3. Volume Profile & POC

- **Data:** 최근 3개월(60일) 간의 매물대 분석.
- **Condition:** 현재 주가가 **POC (Point of Control, 최대 거래 매물대)** 위에 있어야 함.
  - POC 아래에 있으면 악성 매물이 위에 쌓여 있다는 뜻이므로 진입 금지.
