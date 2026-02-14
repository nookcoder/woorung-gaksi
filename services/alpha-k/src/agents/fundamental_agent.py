"""
Alpha-K Agent: Fundamental Valuator (Phase 3B) v2
===================================================
rules/04_fundamental.md 구현체.
Piotroski F-Score, 섹터 상대 PER, DART 리스크 체크.

[v2] Neo4j 경쟁사 비교 분석 추가.
  - 경쟁사 PER 대비 상대적 저평가/고평가 판단
  - 공급망 리스크: 주요 공급업체/고객사의 건전성 체크
"""
import os
import requests
import logging
from typing import Dict, Any, List, Optional

from ..domain.models import FundamentalResult, FundamentalVerdict
from ..infrastructure.data_providers.market_data import MarketDataProvider
from ..infrastructure.graph.graph_service import graph_service

logger = logging.getLogger(__name__)

# DART 공시 리스크 블랙리스트 키워드
DART_BLACKLIST_KEYWORDS = [
    "불성실공시법인", "관리종목지정", "횡령", "배임",
    "감사의견 거절", "감사의견 한정",
]


class FundamentalAgent:
    """
    Phase 3B: 재무 분석.
    1) Piotroski F-Score >= 7 → Pass, < 4 → Fail
    2) Sector Relative PER < 0.8 AND PEG < 1.5
    3) DART Risk Check (블랙리스트 키워드, CB 오버행)
    4) [NEW] Neo4j 경쟁사 PER 비교 → Peer Relative Valuation
    """

    def __init__(
        self,
        opendart_api_key: str = None,
        data: MarketDataProvider = None,
    ):
        self.opendart_api_key = opendart_api_key or os.getenv("OPENDART_API_KEY", "")
        self.data = data or MarketDataProvider()
        self.graph = graph_service

    def analyze(
        self, ticker: str,
        financials: Dict[str, Any],
        sector_avg_per: float = 0,
    ) -> FundamentalResult:
        """재무 분석을 수행하고 FundamentalResult를 반환한다."""

        # ─── 1. Piotroski F-Score ───
        f_score = self._calculate_f_score(financials)

        # ─── 2. Sector Relative PER ───
        stock_per = financials.get("per", 0)

        # [v2] Neo4j 경쟁사 PER로 상대 PER 보강
        if sector_avg_per <= 0:
            sector_avg_per = self._get_peer_avg_per(ticker)

        relative_per = stock_per / sector_avg_per if sector_avg_per > 0 else 999
        peg = financials.get("peg_ratio", 999)

        # ─── 3. DART Risk Check ───
        dart_risks = self._check_dart_risks(ticker)
        cb_overhang = financials.get("cb_overhang_pct", 0)

        # ─── 판정 ───
        data_available = financials.get("data_available", True)

        # ─── 판정 ───
        verdict = self._determine_verdict(f_score, relative_per, peg, dart_risks, cb_overhang, data_available)

        summary = self._build_summary(f_score, verdict, relative_per, peg, dart_risks, cb_overhang, data_available)

        return FundamentalResult(
            ticker=ticker,
            f_score=f_score,
            verdict=verdict,
            relative_per=round(relative_per, 2),
            peg_ratio=peg,
            dart_risks=dart_risks,
            cb_overhang_pct=cb_overhang,
            summary=summary,
        )

    # ──────────────────────────────────────────────────────────────────
    # [NEW] Neo4j 경쟁사 PER 비교
    # ──────────────────────────────────────────────────────────────────

    def _get_peer_avg_per(self, ticker: str) -> float:
        """
        Neo4j에서 경쟁사 목록 → KIS API로 각 경쟁사 PER 조회 → 평균.
        경쟁사 데이터 없으면 테마 동료 종목으로 fallback.
        """
        if not self.graph.is_available:
            return 0

        try:
            # 1차: 경쟁사
            competitors = self.graph.get_competitors(ticker)
            if not competitors:
                # 2차: 테마 동료
                peers = self.graph.get_theme_peers(ticker)
                competitors = peers[:5] if peers else []

            if not competitors:
                return 0

            per_values = []
            for comp in competitors[:5]:  # 최대 5개
                try:
                    info = self.data.get_stock_info(comp["ticker_code"])
                    per = info.get("per", 0)
                    if per and 0 < per < 200:  # 유효한 PER만
                        per_values.append(per)
                except Exception:
                    continue

            if per_values:
                avg_per = sum(per_values) / len(per_values)
                logger.info(
                    f"[FundamentalAgent] Peer avg PER for {ticker}: "
                    f"{avg_per:.1f} (from {len(per_values)} peers)"
                )
                return avg_per

        except Exception as e:
            logger.debug(f"[FundamentalAgent] Peer PER lookup failed: {e}")

        return 0

    # ──────────────────────────────────────────────────────────────────
    # 1. Piotroski F-Score
    # ──────────────────────────────────────────────────────────────────

    def _calculate_f_score(self, f: Dict[str, Any]) -> int:
        """
        Piotroski F-Score (0-9).

        각 1점씩 (04_fundamental.md 기준):
        1. ROA > 0
        2. OCF > 0
        3. ROA 증가 (current > previous)
        4. OCF > Net Income (Quality of Earnings)
        5. Long-term Debt Ratio 감소
        6. Current Ratio 증가
        7. 신주 미발행 (Dilution 없음)
        8. Gross Margin 증가
        9. Asset Turnover 증가
        """
        score = 0

        # 1. Profitability
        if f.get('roa', 0) > 0:
            score += 1
        if f.get('operating_cash_flow', 0) > 0:
            score += 1
        if f.get('roa', 0) > f.get('roa_prev', 0):
            score += 1
        if f.get('operating_cash_flow', 0) > f.get('net_income', 0):
            score += 1

        # 2. Leverage, Liquidity, Source of Funds
        if f.get('long_term_debt', 0) < f.get('long_term_debt_prev', float('inf')):
            score += 1
        if f.get('current_ratio', 0) > f.get('current_ratio_prev', 0):
            score += 1
        if f.get('shares_outstanding', 0) <= f.get('shares_outstanding_prev', float('inf')):
            score += 1

        # 3. Operating Efficiency
        if f.get('gross_margin', 0) > f.get('gross_margin_prev', 0):
            score += 1
        if f.get('asset_turnover', 0) > f.get('asset_turnover_prev', 0):
            score += 1

        return score

    # ──────────────────────────────────────────────────────────────────
    # 3. DART Risk Check
    # ──────────────────────────────────────────────────────────────────

    def _check_dart_risks(self, ticker: str) -> List[str]:
        """
        OpenDART API를 통해 최근 6개월 공시에서 블랙리스트 키워드를 검색한다.
        API Key가 없으면 빈 리스트 반환 (graceful degradation).
        """
        if not self.opendart_api_key:
            logger.info("[FundamentalAgent] No OPENDART_API_KEY → skipping DART check")
            return []

        found_risks: List[str] = []

        try:
            url = "https://opendart.fss.or.kr/api/list.json"
            params = {
                "crtfc_key": self.opendart_api_key,
                "corp_code": self._ticker_to_corp_code(ticker),
                "bgn_de": "",
                "page_count": 100,
            }

            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"[FundamentalAgent] DART API returned {resp.status_code}")
                return []

            data = resp.json()
            if data.get("status") != "000":
                return []

            disclosures = data.get("list", [])
            for disc in disclosures:
                title = disc.get("report_nm", "")
                for keyword in DART_BLACKLIST_KEYWORDS:
                    if keyword in title:
                        found_risks.append(f"{keyword} ({disc.get('rcept_dt', '')})")

        except Exception as e:
            logger.error(f"[FundamentalAgent] DART check failed: {e}")

        return found_risks

    def _ticker_to_corp_code(self, ticker: str) -> str:
        """종목코드 → DART corp_code 변환."""
        # TODO: corp_code.xml 다운로드 후 매핑 로직 구현
        return ticker

    # ──────────────────────────────────────────────────────────────────
    # Verdict
    # ──────────────────────────────────────────────────────────────────

    def _determine_verdict(
        self, f_score: int, rel_per: float, peg: float,
        dart_risks: List[str], cb_overhang: float,
        data_available: bool = True
    ) -> FundamentalVerdict:
        """최종 Pass/Fail/Warning 판정."""
        # Hard Fail 조건
        if dart_risks:
            return FundamentalVerdict.FAIL
            
        # Missing Data Handling
        if not data_available:
            # 데이터가 없으면 FAIL 대신 WARNING 처리 (API 오류 등으로 인한 과도한 필터링 방지)
            return FundamentalVerdict.WARNING

        if f_score < 4:
            return FundamentalVerdict.FAIL

        # Warning 조건
        if cb_overhang > 5.0:
            return FundamentalVerdict.WARNING
        if f_score < 7:
            return FundamentalVerdict.WARNING

        # Pass 조건
        if f_score >= 7:
            if rel_per < 0.8 and peg < 1.5:
                return FundamentalVerdict.PASS
            elif rel_per >= 999 or peg >= 999:
                return FundamentalVerdict.PASS
            else:
                return FundamentalVerdict.WARNING

        return FundamentalVerdict.WARNING

    def _build_summary(
        self, f_score, verdict, rel_per, peg, dart_risks, cb_overhang, data_available=True
    ) -> str:
        parts = []
        if not data_available:
            parts.append("⚠️ Missing Financials")
        else:
            parts.append(f"F-Score: {f_score}/9")
            
        parts.append(f"→ {verdict.value}")
        
        if rel_per < 999:
            parts.append(f"Relative PER: {rel_per:.2f}")
        if peg < 999:
            parts.append(f"PEG: {peg:.2f}")
        if dart_risks:
            parts.append(f"⚠️ DART Risks: {', '.join(dart_risks)}")
        if cb_overhang > 0:
            parts.append(f"CB Overhang: {cb_overhang:.1f}%")
        return " | ".join(parts)
