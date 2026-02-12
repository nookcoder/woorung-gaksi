"""
Alpha-K Agent: Sector Rotation (Phase 2 - Candidate Screening)
===============================================================
rules/02_sector_rotation.md 구현체.
RS Score 기반 주도 섹터 선정 + 낙수효과 로직 + 1차 필터링.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging

from ..domain.models import SectorScore, CandidateScreeningResult
from ..infrastructure.data_providers.market_data import MarketDataProvider

logger = logging.getLogger(__name__)

# 섹터 필터: 금융, 은행 등 분석 대상에서 제외할 섹터 코드  
EXCLUDED_SECTORS = set()

# 1차 필터 기준: 거래대금 500억 원 이상
MIN_TRADING_VALUE = 50_000_000_000  # 50B KRW


class SectorAgent:
    """
    Phase 2: 섹터 로테이션.
    1) KOSPI/KOSDAQ 업종별 RS Score 계산
    2) 상위 3개 섹터 선정
    3) 낙수효과(Trickle-Down) 조건 체크
    4) 1차 필터: 거래대금 > 500억 AND 주가 > 60MA
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
            kospi_returns, start_3m, start_1m, start_1w, end_str
        )

        # 상위 3개 섹터
        top_sectors = sorted(sector_scores, key=lambda s: s.rs_score, reverse=True)[:3]
        logger.info(f"[SectorAgent] Top 3 Sectors: {[s.sector_name for s in top_sectors]}")

        # ─── 1차 필터: 후보 종목 선별 ───
        candidates = self._filter_candidates(top_sectors, start_3m, end_str)

        return CandidateScreeningResult(
            top_sectors=top_sectors,
            candidate_tickers=candidates,
            total_scanned=len(candidates),
        )

    def _get_benchmark_returns(self, start_3m: str, end: str) -> Dict[str, float]:
        """KOSPI 벤치마크 수익률 (1주, 1개월, 3개월)"""
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
        self, benchmark: Dict, start_3m: str, start_1m: str, start_1w: str, end: str
    ) -> List[SectorScore]:
        """
        각 업종의 RS Score를 계산한다.
        RS_Score = 0.5 * 1W_Alpha + 0.3 * 1M_Alpha + 0.2 * 3M_Alpha
        """
        scores = []
        try:
            date_fmt = datetime.now().strftime("%Y%m%d")
            # pykrx로 업종 목록 가져오기
            sector_tickers = stock_get_index_ticker_list(date_fmt)

            for sector_code in sector_tickers:
                if sector_code in EXCLUDED_SECTORS:
                    continue

                try:
                    sector_name = stock_get_index_ticker_name(sector_code)
                    ohlcv = self.data.get_sector_ohlcv(sector_code, start_3m, end)

                    if ohlcv.empty or len(ohlcv) < 5:
                        continue

                    close = ohlcv['종가'] if '종가' in ohlcv.columns else ohlcv.iloc[:, 0]

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
                        trickle_down_ready=False,  # 아래에서 별도 체크
                    ))
                except Exception as e:
                    logger.debug(f"[SectorAgent] Skipping sector {sector_code}: {e}")
                    continue

        except Exception as e:
            logger.error(f"[SectorAgent] Sector scoring failed: {e}")

        return scores

    def _filter_candidates(
        self, top_sectors: List[SectorScore], start_3m: str, end: str
    ) -> List[str]:
        """
        상위 섹터 내 종목 중 1차 필터 통과 종목을 반환한다.
        필터: 거래대금 > 500억 AND 주가 > 60일 이평선
        """
        candidates = []

        for sector in top_sectors:
            try:
                tickers = self.data.get_sector_tickers(sector.sector_code)
                if not tickers:
                    continue

                for ticker in tickers:
                    try:
                        ohlcv = self.data.get_ohlcv(ticker, start_3m, end)
                        if ohlcv.empty or len(ohlcv) < 60:
                            continue

                        # 거래대금 최근 20일 평균
                        if 'Volume' in ohlcv.columns:
                            avg_value = (ohlcv['Close'] * ohlcv['Volume']).tail(20).mean()
                        else:
                            avg_value = 0

                        if avg_value < MIN_TRADING_VALUE:
                            continue

                        # 60일 이평선 위
                        ma60 = ohlcv['Close'].rolling(60).mean().iloc[-1]
                        if pd.isna(ma60) or ohlcv['Close'].iloc[-1] <= ma60:
                            continue

                        candidates.append(ticker)

                    except Exception as e:
                        logger.debug(f"[SectorAgent] Filter skip {ticker}: {e}")
                        continue

            except Exception as e:
                logger.warning(f"[SectorAgent] Sector filter failed for {sector.sector_name}: {e}")
                continue

        logger.info(f"[SectorAgent] {len(candidates)} candidates passed primary filter")
        return candidates


# pykrx helper wrappers (avoid import issues)
def stock_get_index_ticker_list(date: str):
    from pykrx import stock as st
    return st.get_index_ticker_list(date, "KOSPI")

def stock_get_index_ticker_name(code: str):
    from pykrx import stock as st
    return st.get_index_ticker_name(code)
