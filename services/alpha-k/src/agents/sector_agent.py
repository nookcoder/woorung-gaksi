"""
Alpha-K Agent: Sector Rotation (Phase 2 - Candidate Screening)
===============================================================
rules/02_sector_rotation.md 구현체.
RS Score 기반 주도 섹터 선정 + 낙수효과 로직 + 1차 필터링.

데이터 소스: KIS Open API (업종 시세)
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging

from ..domain.models import SectorScore, CandidateScreeningResult
from ..infrastructure.data_providers.market_data import MarketDataProvider

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
    # "0018": "금융업", # 스윙 전략에서 제외 선호
    "0022": "서비스업",
    "0024": "제조업",
    # 코스닥 업종 (필요시 추가)
    "1012": "IT 종합",
    "1015": "제조",
}

# 1차 필터 기준: 거래대금 100억 원 이상
MIN_TRADING_VALUE = 10_000_000_000  # 10B KRW


class SectorAgent:
    """
    Phase 2: 섹터 로테이션.
    1) KOSPI/KOSDAQ 업종별 RS Score 계산 (KIS API)
    2) 상위 3개 섹터 선정
    3) 1차 필터: 매입 대상 종목 선별 (거래대금 > 100억 AND 주가 > 60MA * 0.95)
    """

    def __init__(self, data: MarketDataProvider = None):
        self.data = data or MarketDataProvider()

    def analyze(self) -> CandidateScreeningResult:
        """섹터 스크리닝을 실행한다."""
        end = datetime.now()
        end_str = end.strftime("%Y-%m-%d")
        start_3m = (end - timedelta(days=90)).strftime("%Y-%m-%d")
        start_1m = (end - timedelta(days=30)).strftime("%Y-%m-%d")
        start_1w = (end - timedelta(days=7)).strftime("%Y-%m-%d")

        # ─── 벤치마크 수익률 (KOSPI) ───
        kospi_returns = self._get_benchmark_returns(start_3m, end_str)

        # ─── 섹터 RS 점수 계산 ───
        sector_scores = self._score_sectors(
            kospi_returns, start_3m, end_str
        )

        # 상위 3개 섹터
        top_sectors = sorted(sector_scores, key=lambda s: s.rs_score, reverse=True)[:3]
        logger.info(f"[SectorAgent] Top 3 Sectors: {[s.sector_name for s in top_sectors]}")

        # ─── 1차 필터: 후보 종목 선별 ───
        candidates = self._filter_candidates(top_sectors, start_3m, end_str)

        # ─── LLM Sector Theme Analysis ───
        self._analyze_sector_themes(top_sectors)

        return CandidateScreeningResult(
            top_sectors=top_sectors,
            candidate_tickers=candidates,
            total_scanned=len(candidates),
        )

    def _analyze_sector_themes(self, top_sectors: List[SectorScore]):
        """LLM을 사용하여 상위 섹터의 상승 이유(테마)를 추론한다."""
        try:
            from ..infrastructure.llm_client import llm_client
            llm = llm_client.get_agent_llm("sector")
            if not llm:
                return

            sector_names = [s.sector_name for s in top_sectors]
            prompt = (
                f"The following sectors are currently leading the Korean stock market based on RS Score: {', '.join(sector_names)}.\n"
                f"Briefly explain the potential reasons or themes driving these sectors right now (e.g., AI boom, policy changes, seasonality)."
            )
            
            # 비동기로 실행하거나 결과를 어딘가에 저장하면 좋지만, 
            # 현재 구조상 로그에 남기거나 추후 리포트 단계에서 활용하도록 설계
            response = llm.invoke(prompt)
            logger.info(f"[SectorAgent] LLM Insight:\n{response.content}")
            
        except Exception as e:
            logger.warning(f"[SectorAgent] LLM theme analysis failed: {e}")

    def _get_benchmark_returns(self, start_3m: str, end: str) -> Dict[str, float]:
        """KOSPI 벤치마크 수익률 (1주, 1개월, 3개월). FDR 사용."""
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
        """
        주요 업종의 RS Score를 계산한다.
        RS_Score = 0.5 * 1W_Alpha + 0.3 * 1M_Alpha + 0.2 * 3M_Alpha
        """
        scores = []
        for sector_code, sector_name in KIS_SECTORS.items():
            try:
                ohlcv = self.data.get_sector_daily(sector_code, start_3m, end)
                if ohlcv.empty or len(ohlcv) < 5:
                    continue

                close = ohlcv['Close']

                # 구간별 수익률
                ret_1w = (close.iloc[-1] / close.iloc[-min(5, len(close))]) - 1
                ret_1m = (close.iloc[-1] / close.iloc[-min(20, len(close))]) - 1
                ret_3m = (close.iloc[-1] / close.iloc[0]) - 1

                # Alpha = Sector Return - Benchmark Return
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
        """
        상위 섹터 내 종목 중 1차 필터 통과 종목을 반환한다.
        필터: 거래대금 > 100억 AND 주가 > 60일 이평선 * 0.95
        """
        candidates = []
        for sector in top_sectors:
            try:
                tickers = self.data.get_sector_tickers(sector.sector_code)
                if not tickers:
                    continue

                for ticker in tickers[:50]: # 섹터별 상위 종목만 우선 샘플링 (부하 방지)
                    try:
                        # KIS에서 종목 현재가/거래대금 바로 가져오기
                        info = self.data.get_stock_info(ticker)
                        if not info:
                            continue
                        
                        # 거래대금 필터 (KIS: 억원 단위 → 원 단위 변환)
                        trading_value = info.get("trading_value", 0) * 100_000_000
                        if trading_value < MIN_TRADING_VALUE:
                            continue

                        # OHLCV 가져와서 60MA 체크
                        ohlcv = self.data.get_ohlcv(ticker, start_3m, end)
                        if ohlcv.empty or len(ohlcv) < 60:
                            continue

                        ma60 = ohlcv['Close'].rolling(60).mean().iloc[-1]
                        if pd.isna(ma60) or ohlcv['Close'].iloc[-1] <= ma60 * 0.95:
                            continue

                        if ticker not in candidates:
                            candidates.append(ticker)

                    except Exception as e:
                        logger.debug(f"[SectorAgent] Filter skip {ticker}: {e}")
                        continue

            except Exception as e:
                logger.warning(f"[SectorAgent] Sector filter failed for {sector.sector_name}: {e}")
                continue

        logger.info(f"[SectorAgent] {len(candidates)} candidates passed primary filter")
        return candidates
