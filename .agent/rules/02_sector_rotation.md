---
trigger: model_decision
description: "Alpha-K 프로젝트 요구사항 명세서"를 바탕으로 구현해달라고 부탁할 때 참고해야함
---

# Rule: Sector Rotation & Theme Hunting

돈이 몰리는 주도 섹터를 식별하고, 그 안에서 대장주와 부대장주를 가려내는 로직이다.

## 1. Relative Strength (RS) Scoring

단순 등락률이 아닌, 시장(Benchmark) 대비 초과 수익률(Alpha)을 기반으로 점수를 매긴다.

- **Formula:**
  `RS_Score = (0.5 * 1W_Alpha) + (0.3 * 1M_Alpha) + (0.2 * 3M_Alpha)`
  - Where `Alpha` = (Sector Return - KOSPI Return)
- **Selection:** 상위 3개 섹터만 타겟팅한다.

## 2. Trickle-Down Logic (Nak-Su Effect)

섹터 내 자금 흐름의 순서를 판단한다.

- **Condition:**
  1. 섹터 시총 상위 3개 종목(Large Cap)이 모두 20일 이평선 위에 위치.
  2. 섹터 지수 거래량이 전주 대비 20% 이상 증가.
  - **Action:** 위 조건 만족 시, 해당 섹터 내 '중소형주(Small Cap)' 중 첫 번째 상승 파동이 나오는 종목을 최우선으로 선정한다.
