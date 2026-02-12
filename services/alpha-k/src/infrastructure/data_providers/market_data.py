"""
Alpha-K Infrastructure: Market Data Provider
=============================================
KIS Open API + FinanceDataReader 통합 데이터 제공.

우선순위:
  1차. KIS API (투자자 수급, PER/PBR, 업종 시세)
  2차. FinanceDataReader (OHLCV, 지수, 환율, ADR)
"""
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import logging

from .kis_client import KISClient

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """주가, 지수, 환율, 수급 데이터를 통합 제공한다."""

    def __init__(self, kis_client: KISClient = None):
        self.kis = kis_client or KISClient()

    # ───── Price Data (FDR Primary / KIS Fallback) ─────

    @staticmethod
    def get_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
        """종목 OHLCV. FDR 우선 (장기 과거 데이터에 강함)."""
        try:
            df = fdr.DataReader(ticker, start, end)
            if df.empty:
                logger.warning(f"[MarketData] Empty OHLCV for {ticker}")
            return df
        except Exception as e:
            logger.error(f"[MarketData] OHLCV fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_index(index_code: str, start: str, end: str) -> pd.DataFrame:
        """지수 데이터 (KS11, KQ11 등) — FDR 사용."""
        try:
            return fdr.DataReader(index_code, start, end)
        except Exception as e:
            logger.error(f"[MarketData] Index fetch failed for {index_code}: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_usd_krw(start: str, end: str) -> pd.DataFrame:
        """USD/KRW 환율 데이터."""
        try:
            return fdr.DataReader("USD/KRW", start, end)
        except Exception as e:
            logger.error(f"[MarketData] USD/KRW fetch failed: {e}")
            return pd.DataFrame()

    # ───── V-KOSPI (FDR) ─────

    @staticmethod
    def get_vkospi(start: str, end: str) -> pd.DataFrame:
        """V-KOSPI (KOSPI 200 변동성 지수). FDR DataReader 사용."""
        try:
            df = fdr.DataReader("VKOSPI", start, end)
            return df
        except Exception as e:
            logger.warning(f"[MarketData] V-KOSPI fetch failed: {e}")
            return pd.DataFrame()

    # ───── Market Breadth (ADR) ─────

    @staticmethod
    def get_advancing_declining(market: str = "KOSPI") -> Tuple[int, int]:
        """
        상승/하락 종목 수 반환. ADR 계산용.
        FDR StockListing 사용 (오늘 기준 스냅샷).
        """
        try:
            df = fdr.StockListing(market)
            if df.empty:
                return 0, 0

            if 'ChagesRatio' in df.columns:
                changes = df['ChagesRatio']
            elif 'Changes' in df.columns:
                changes = df['Changes']
            elif 'Close' in df.columns and 'Open' in df.columns:
                changes = df['Close'] - df['Open']
            else:
                return 0, 0

            advancing = int((changes > 0).sum())
            declining = int((changes < 0).sum())
            return advancing, declining
        except Exception as e:
            logger.warning(f"[MarketData] ADR StockListing failed: {e}")
            return 0, 0

    # ───── Investor / Smart Money (KIS API) ─────

    def get_investor_trading(self, ticker: str) -> pd.DataFrame:
        """
        종목별 투자자 매매동향 (외국인/기관/개인).
        KIS API [FHKST01010900] 사용.
        """
        if not self.kis.is_configured:
            logger.warning("[MarketData] KIS API key not configured → no investor data")
            return pd.DataFrame()

        try:
            return self.kis.get_investor_trading(ticker)
        except Exception as e:
            logger.error(f"[MarketData] Investor trading failed for {ticker}: {e}")
            return pd.DataFrame()

    def get_program_trading(self, ticker: str) -> dict:
        """프로그램 매매 (비차익/차익). KIS API [FHKST01010200]."""
        if not self.kis.is_configured:
            return {}
        try:
            return self.kis.get_program_trading(ticker)
        except Exception as e:
            logger.error(f"[MarketData] Program trading failed for {ticker}: {e}")
            return {}

    # ───── Sector Data (KIS API / FDR Fallback) ─────

    def get_sector_daily(
        self, sector_code: str, start: str, end: str
    ) -> pd.DataFrame:
        """
        업종 기간별 시세. KIS API [FHKUP03500100] 사용.
        KIS 미설정 시 FDR fallback.
        """
        if self.kis.is_configured:
            try:
                df = self.kis.get_sector_daily(sector_code, start, end)
                if not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"[MarketData] KIS sector daily failed: {e}")

        # FDR fallback (KRX 업종코드 → FDR에서는 지원 제한적)
        try:
            df = fdr.DataReader(sector_code, start, end)
            return df
        except Exception:
            return pd.DataFrame()

    def get_sector_index(self, sector_code: str) -> dict:
        """업종 현재 지수. KIS API."""
        if not self.kis.is_configured:
            return {}
        try:
            return self.kis.get_sector_index(sector_code)
        except Exception as e:
            logger.error(f"[MarketData] Sector index failed: {e}")
            return {}

    def get_sector_tickers(self, sector_code: str) -> List[str]:
        """업종별 종목 리스트. KIS API."""
        if not self.kis.is_configured:
            return []
        try:
            return self.kis.get_sector_tickers(sector_code)
        except Exception as e:
            logger.error(f"[MarketData] Sector tickers failed for {sector_code}: {e}")
            return []

    # ───── Fundamental (KIS API) ─────

    def get_stock_info(self, ticker: str) -> dict:
        """
        종목 기본 정보 (PER, PBR, EPS, 시총, 거래대금 등).
        KIS API [FHKST01010100] 사용.
        """
        if not self.kis.is_configured:
            logger.warning("[MarketData] KIS API key not configured → no stock info")
            return {}

        try:
            return self.kis.get_stock_info(ticker)
        except Exception as e:
            logger.error(f"[MarketData] Stock info failed for {ticker}: {e}")
            return {}

    def get_financial_statements(self, ticker: str) -> dict:
        """재무제표 요약. KIS API."""
        if not self.kis.is_configured:
            return {}
        try:
            return self.kis.get_financial_statements(ticker)
        except Exception as e:
            logger.error(f"[MarketData] Financial statements failed for {ticker}: {e}")
            return {}

    @staticmethod
    def get_stock_listing(market: str = "KOSPI") -> pd.DataFrame:
        """전 종목 스냅샷. FDR StockListing 사용."""
        try:
            return fdr.StockListing(market)
        except Exception as e:
            logger.error(f"[MarketData] StockListing failed: {e}")
            return pd.DataFrame()
