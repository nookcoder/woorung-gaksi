---
trigger: model_decision
description: "Alpha-K 프로젝트 요구사항 명세서"를 바탕으로 구현해달라고 부탁할 때 참고해야함
---

# Rule: Fundamental & Valuation Filter

재무적 안전마진을 확보하고, 부실 기업(똥 밟기)을 원천 차단한다.

## 1. Piotroski F-Score (Quality Check)

9점 만점의 재무 건전성 지표.

- **Threshold:** F-Score >= 7 (Pass). F-Score < 4 (Fail/Exclude).
- **Criteria (1 point each):**
  1. ROA > 0
  2. Operating Cash Flow (OCF) > 0
  3. ROA (Current) > ROA (Previous)
  4. OCF > Net Income (Quality of Earnings)
  5. Long-term Debt Ratio decreased
  6. Current Ratio increased
  7. No new shares issued (Dilution check)
  8. Gross Margin increased
  9. Asset Turnover increased

## 2. Sector Relative Valuation

- **Formula:** `Relative PER = (Stock PER / Sector Average PER)`
- **Condition:** `Relative PER < 0.8` (섹터 평균 대비 20% 이상 저평가) AND `PEG Ratio < 1.5`

## 3. DART Risk Check (Critical)

- **Action:** OpenDART API를 통해 최근 6개월 공시 검색.
- **Blacklist Keywords:** "불성실공시법인", "관리종목지정", "횡령", "배임", "감사의견 거절/한정".
- **Overhang Check:** 전환사채(CB) 잔액이 시가총액의 5% 이상인 경우 경고(Warning).
