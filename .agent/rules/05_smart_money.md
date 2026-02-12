---
trigger: model_decision
description: "Alpha-K 프로젝트 요구사항 명세서"를 바탕으로 구현해달라고 부탁할 때 참고해야함
---

# Rule: Smart Money Flow & Sentiment

수급의 질(Quality)을 분석하여 진짜 세력의 개입 여부를 판단한다.

## 1. Program Non-Arbitrage Buying

- **Logic:** 장중(09:30 ~ 14:00) '프로그램 비차익 순매수'가 지속적으로 유입되는지 확인.
- **Signal:** 프로그램 순매수 대금 누적 그래프가 우상향(Positive Slope)일 것.

## 2. Broker Window Analysis (Foreign/Institutional)

- **Logic:** 거래원 상위 5개사(Top 5 Brokers) 분석.
- **Positive Signal:**
  - Buyer: Morgan Stanley, JP Morgan, Goldman Sachs, CS (Foreign) OR Shinhan, Samsung (Domestic Inst.)
  - Seller: Kiwoom, Mirae Asset (Retail dominant)
- **Condition:** (Foreign/Inst Buy Volume) > (Retail Buy Volume \* 2)

## 3. Continuous Accumulation

- **Logic:** 최근 5거래일 중 기관(Institutional) 또는 외국인(Foreign) 순매수가 3일 이상 발생.
