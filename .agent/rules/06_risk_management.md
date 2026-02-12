---
trigger: model_decision
description: "Alpha-K 프로젝트 요구사항 명세서"를 바탕으로 구현해달라고 부탁할 때 참고해야함
---

# Rule: Risk Management & Execution

자금 관리와 청산(Exit) 전략. 이 규칙은 타협 불가(Non-negotiable)하다.

## 1. Position Sizing (Pyramiding)

한 번에 전액 매수하지 않고, 수익이 날 때만 불타기를 한다.

- **Entry 1:** 30% Allocation (Initial Entry)
- **Entry 2:** 30% Allocation (When Profit > +3%)
- **Entry 3:** 40% Allocation (When Profit > +5%)
- **Note:** 추가 진입 시, 평단가가 높아지므로 손절 라인(Stop Loss)도 반드시 위로 올려야 함 (Trailing Stop).

## 2. Dynamic Stop Loss (ATR Based)

- **Formula:** `Stop Price = Average Entry Price - (3 * ATR(14))`
- **Logic:** 변동성이 큰 종목은 손절폭을 넓게, 작은 종목은 좁게 가져간다. 고정 % 손절(예: -3%)보다 휩소(Whipsaw)에 강하다.

## 3. Risk/Reward Ratio (R/R)

- **Pre-Entry Check:**
  `Potential Reward (to Next Resistance) / Risk (to Stop Price) >= 2.0`
- 이 조건을 만족하지 않으면 차트가 아무리 좋아도 진입하지 않는다.
