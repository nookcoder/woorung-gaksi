"""
Alpha-K Agent: Sector Rotation (Phase 2 - Candidate Screening) v2
==================================================================
rules/02_sector_rotation.md 구현체.

[v2] Neo4j 테마 기반 분석 + TimescaleDB 데이터 활용.

데이터 소스:
  - Neo4j:       테마 → 종목 매핑, 테마 모멘텀 분석
  - TimescaleDB: OHLCV (거래대금, 이동평균선), 섹터 지수
  - KIS API:     업종 시세 (TimescaleDB fallback)
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging

from ..domain.models import SectorScore, CandidateScreeningResult
from ..infrastructure.data_providers.market_data import MarketDataProvider
from ..infrastructure.graph.graph_service import graph_service
from ..infrastructure.graph.event_service import event_service

logger = logging.getLogger(__name__)

# KIS KRX 업종 코드 (0001=KOSPI 종합 제외 주요 섹터)
KIS_SECTORS = {
    "0002": "음식료품",
    "0003": "섬유/의복",
    "0004": "종이/목재",
    "0005": "화학",
    "0006": "의약품",
    "0007": "비금속광물",
    "0008": "철강금속",
    "0009": "기계",
    "0010": "전기/전자",
    "0011": "의료정밀",
    "0012": "운수장비",
    "0013": "유통업",
    "0014": "전기가스업",
    "0015": "건설업",
    "0016": "운수창고",
    "0017": "통신업",
    "0022": "서비스업",
    "0024": "제조업",
    "1012": "IT 종합",
    "1015": "제조",
}

# 1차 필터 기준: 거래대금 100억 원 이상
MIN_TRADING_VALUE = 10_000_000_000  # 10B KRW


class SectorAgent:
    """
    Phase 2: 섹터 로테이션 + 테마 분석.

    [기존] 업종별 RS Score → 상위 3개 섹터 → 1차 필터
    [신규] Neo4j 테마 매핑 → 테마 모멘텀 + 뉴스 이벤트(GraphRAG) 분석 → 테마기반 후보 확장
    """

    def __init__(self, data: MarketDataProvider = None):
        self.data = data or MarketDataProvider()
        self.graph = graph_service
        self.event_service = event_service

    def analyze(self) -> CandidateScreeningResult:
        """섹터 스크리닝 + 테마 분석을 실행한다."""
        # Time-Travel 지원: Provider에 설정된 날짜가 있으면 사용
        current_date = getattr(self.data, 'current_date', None) or datetime.now()
        end_str = current_date.strftime("%Y-%m-%d")
        start_3m_dt = current_date - timedelta(days=90)
        start_3m = start_3m_dt.strftime("%Y-%m-%d")

        # ─── 1. 벤치마크 수익률 (KOSPI) ───
        kospi_returns = self._get_benchmark_returns(start_3m, end_str)

        # ─── 2. 섹터 RS 점수 계산 ───
        sector_scores = self._score_sectors(kospi_returns, start_3m, end_str)

        # 상위 3개 섹터
        top_sectors = sorted(sector_scores, key=lambda s: s.rs_score, reverse=True)[:3]
        logger.info(f"[SectorAgent] Top 3 Sectors: {[s.sector_name for s in top_sectors]}")

        # ─── 3. KIS 업종 기반 후보 ───
        candidates = self._filter_candidates(top_sectors, start_3m, end_str)
        logger.info(f"[SectorAgent] KIS sector candidates: {len(candidates)}")

        # ─── 4. [NEW] Neo4j 테마 + Event Impact 기반 후보 확장 ───
        theme_candidates = self._get_theme_candidates(
            candidates, start_3m, end_str, current_date=end_str
        )
        for tc in theme_candidates:
            if tc not in candidates:
                candidates.append(tc)
        logger.info(
            f"[SectorAgent] After theme expansion: {len(candidates)} "
            f"(+{len(theme_candidates)} from themes)"
        )

        # ─── 5. LLM Sector + Theme Insight ───
        self._analyze_sector_themes(top_sectors)

        return CandidateScreeningResult(
            top_sectors=top_sectors,
            candidate_tickers=candidates,
            total_scanned=len(candidates),
        )

    # ─────────────────────────────────────────────
    # [NEW] Neo4j 테마 기반 후보 확장
    # ─────────────────────────────────────────────

    def _get_theme_candidates(
        self, existing_candidates: List[str], start_3m: str, end_str: str, current_date: str = None
    ) -> List[str]:
        """
        Neo4j 테마 기반 후보 확장.
        1) 기존 후보 종목이 속한 테마 조회
        2) 해당 테마의 다른 종목(동료) 중 1차 필터 통과 종목 추가
        3) 모멘텀 + 뉴스 호재(GraphRAG)가 좋은 테마의 종목도 추가
        """
        if not self.graph.is_available:
            logger.warning("[SectorAgent] Neo4j not available, skipping theme expansion")
            return []

        theme_tickers = []

        # ──── 방법 1: 기존 후보 종목의 테마 동료 확장 ────
        seen_themes = set()
        for ticker in existing_candidates[:10]:  # 상위 10개만 (부하 방지)
            try:
                themes = self.graph.get_ticker_themes(ticker)
                for theme_name in themes:
                    if theme_name in seen_themes:
                        continue
                    seen_themes.add(theme_name)

                    peers = self.graph.get_theme_momentum_candidates(theme_name)
                    for peer in peers:
                        if peer not in existing_candidates and peer not in theme_tickers:
                            theme_tickers.append(peer)
            except Exception as e:
                logger.debug(f"[SectorAgent] Theme peer lookup failed for {ticker}: {e}")

        # ──── 방법 2: 모멘텀 + 이벤트 파급력이 좋은 테마 종목 추가 ────
        try:
            top_themes = self.graph.get_top_themes_with_tickers(limit=5)
            for theme_data in top_themes:
                theme_name = theme_data.get("theme_name", "")
                if theme_name in seen_themes:
                    continue

                tickers_in_theme = theme_data.get("tickers", [])
                
                # 1. Price Momentum
                price_momentum = self._calculate_theme_momentum(
                    [t["code"] for t in tickers_in_theme[:10]],
                    start_3m, end_str
                )
                
                # 2. Event Impact (GraphRAG)
                if current_date:
                    event_impact = self.event_service.get_theme_impact(theme_name, current_date, days=7)
                else:
                    event_impact = 0.0

                # Combined Score
                # Price Momentum > 2% OR Event Impact > 0.5 (Positive Sentiment)
                if price_momentum > 0.02 or event_impact > 0.5:
                    logger.info(f"  ✨ Theme '{theme_name}' Selected: Mom={price_momentum:.1%} Impact={event_impact:.1f}")
                    seen_themes.add(theme_name)
                    
                    for t in tickers_in_theme:
                        code = t["code"]
                        if (code not in existing_candidates and
                                code not in theme_tickers):
                            theme_tickers.append(code)
                            
        except Exception as e:
            logger.debug(f"[SectorAgent] Theme momentum scan failed: {e}")

        # ──── 1차 필터 적용 (거래대금 + 60MA) ────
        filtered = self._batch_filter_tickers(theme_tickers, start_3m, end_str)
        logger.info(
            f"[SectorAgent] Theme expansion: {len(theme_tickers)} raw → "
            f"{len(filtered)} after filter"
        )
        return filtered

    def _calculate_theme_momentum(
        self, tickers: List[str], start: str, end: str
    ) -> float:
        """테마 종목들의 평균 3개월 수익률 계산 (TimescaleDB batch)."""
        ohlcv_map = self.data.get_ohlcv_batch(tickers, start, end)
        if not ohlcv_map:
            return 0.0

        returns = []
        for ticker, df in ohlcv_map.items():
            if df.empty or len(df) < 5:
                continue
            try:
                ret = (df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1
                if not np.isnan(ret):
                    returns.append(float(ret))
            except:
                pass

        return np.mean(returns) if returns else 0.0

    def _batch_filter_tickers(
        self, tickers: List[str], start_3m: str, end_str: str
    ) -> List[str]:
        """TimescaleDB batch 조회 → 거래대금 + 60MA 필터."""
        if not tickers:
            return []

        ohlcv_map = self.data.get_ohlcv_batch(tickers, start_3m, end_str)
        passed = []

        for ticker, df in ohlcv_map.items():
            try:
                if df.empty or len(df) < 60:
                    continue

                # 거래대금 필터
                if 'trading_value' in df.columns:
                    recent_tv = pd.to_numeric(
                        df['trading_value'].tail(5), errors='coerce'
                    ).mean()
                    if recent_tv < MIN_TRADING_VALUE:
                        continue

                # 60MA 필터
                ma60 = df['Close'].rolling(60).mean().iloc[-1]
                current_price = df['Close'].iloc[-1]
                
                # 조건: 현재가가 60MA의 95% 이상이어야 함 (역배열 심하면 제외)
                if pd.isna(ma60) or current_price <= ma60 * 0.95:
                    continue

                passed.append(ticker)
            except Exception:
                continue

        return passed

    # ─────────────────────────────────────────────
    # 기존 로직 (업종 기반)
    # ─────────────────────────────────────────────

    def _analyze_sector_themes(self, top_sectors: List[SectorScore]):
        """LLM을 사용하여 상위 섹터의 상승 이유(테마)를 추론한다."""
        try:
            from ..infrastructure.llm_client import llm_client
            llm = llm_client.get_agent_llm("sector")
            if not llm:
                return

            sector_names = [s.sector_name for s in top_sectors]

            # [NEW] Neo4j 테마 정보 추가
            theme_info = ""
            if self.graph.is_available:
                all_themes = self.graph.get_all_themes()
                theme_names = [t["theme_name"] for t in all_themes[:15]]
                theme_info = f"\nActive investment themes in the market: {', '.join(theme_names)}"

            prompt = (
                f"The following sectors are currently leading the Korean stock market "
                f"based on RS Score: {', '.join(sector_names)}.{theme_info}\n\n"
                f"Briefly explain the potential reasons or themes driving these sectors "
                f"right now (e.g., AI boom, policy changes, seasonality)."
            )

            response = llm.invoke(prompt)
            logger.info(f"[SectorAgent] LLM Insight:\n{response.content}")

        except Exception as e:
            logger.warning(f"[SectorAgent] LLM theme analysis failed: {e}")

    def _get_benchmark_returns(self, start_3m: str, end: str) -> Dict[str, float]:
        """KOSPI 벤치마크 수익률 (1주, 1개월, 3개월)."""
        try:
            kospi = self.data.get_index("KS11", start_3m, end)
            if kospi.empty:
                return {"1w": 0, "1m": 0, "3m": 0}

            close = kospi['Close']
            ret_1w = (close.iloc[-1] / close.iloc[-min(5, len(close))]) - 1 if len(close) >= 5 else 0
            ret_1m = (close.iloc[-1] / close.iloc[-min(20, len(close))]) - 1 if len(close) >= 20 else 0
            ret_3m = (close.iloc[-1] / close.iloc[0]) - 1

            return {"1w": float(ret_1w), "1m": float(ret_1m), "3m": float(ret_3m)}
        except Exception as e:
            logger.error(f"[SectorAgent] Benchmark returns failed: {e}")
            return {"1w": 0, "1m": 0, "3m": 0}

    def _score_sectors(
        self, benchmark: Dict, start_3m: str, end: str
    ) -> List[SectorScore]:
        """주요 업종의 RS Score를 계산한다. (TimescaleDB sector_indices 활용)"""
        scores = []
        for sector_code, sector_name in KIS_SECTORS.items():
            try:
                ohlcv = self.data.get_sector_daily(sector_code, start_3m, end)
                if ohlcv.empty or len(ohlcv) < 5:
                    continue

                close = ohlcv['Close']

                ret_1w = (close.iloc[-1] / close.iloc[-min(5, len(close))]) - 1
                ret_1m = (close.iloc[-1] / close.iloc[-min(20, len(close))]) - 1
                ret_3m = (close.iloc[-1] / close.iloc[0]) - 1

                alpha_1w = float(ret_1w) - benchmark["1w"]
                alpha_1m = float(ret_1m) - benchmark["1m"]
                alpha_3m = float(ret_3m) - benchmark["3m"]

                rs_score = 0.5 * alpha_1w + 0.3 * alpha_1m + 0.2 * alpha_3m

                scores.append(SectorScore(
                    sector_name=sector_name,
                    sector_code=sector_code,
                    rs_score=rs_score,
                    alpha_1w=alpha_1w,
                    alpha_1m=alpha_1m,
                    alpha_3m=alpha_3m,
                    trickle_down_ready=False,
                ))
            except Exception as e:
                logger.debug(f"[SectorAgent] Skipping sector {sector_code}: {e}")
                continue

        return scores

    def _filter_candidates(
        self, top_sectors: List[SectorScore], start_3m: str, end: str
    ) -> List[str]:
        """상위 섹터 내 종목 중 1차 필터 통과 종목을 반환한다."""
        candidates = []
        for sector in top_sectors:
            try:
                tickers = self.data.get_sector_tickers(sector.sector_code)
                if not tickers:
                    continue

                # [v2] TimescaleDB batch 조회로 개별 API 호출 감소
                filtered = self._batch_filter_tickers(
                    tickers[:50], start_3m, end
                )
                for t in filtered:
                    if t not in candidates:
                        candidates.append(t)

            except Exception as e:
                logger.warning(
                    f"[SectorAgent] Sector filter failed for {sector.sector_name}: {e}"
                )
                continue

        logger.info(f"[SectorAgent] {len(candidates)} candidates passed primary filter")
        return candidates
