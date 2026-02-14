"""
Alpha-K Infrastructure: Market Data Provider (v2)
==================================================
TimescaleDB-first 아키텍처.

데이터 조회 우선순위:
  1차. TimescaleDB (과거 + 적재된 데이터)
  2차. KIS API     (실시간 데이터 / TimescaleDB fallback)
  3차. FDR         (TimescaleDB에 없는 장기 과거 데이터)
"""
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict
import logging

from .kis_client import KISClient
from ..db.db_client import db_client

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """주가, 지수, 환율, 수급 데이터를 통합 제공한다. (TimescaleDB-first)"""

    def __init__(self, kis_client: KISClient = None):
        self.kis = kis_client or KISClient()
        self.db = db_client

    # ═════════════════════════════════════════════
    # OHLCV (TimescaleDB → FDR fallback)
    # ═════════════════════════════════════════════

    def get_ohlcv(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """
        종목 OHLCV. TimescaleDB 우선 → FDR fallback.
        Returns: DatetimeIndex DataFrame with [Open, High, Low, Close, Volume] columns.
        """
        df = self._get_ohlcv_from_db(ticker, start, end)
        if df is not None and not df.empty and len(df) >= 5:
            return df

        # Fallback: FDR
        logger.debug(f"[MarketData] TimescaleDB miss for {ticker}, falling back to FDR")
        return self._get_ohlcv_from_fdr(ticker, start, end)

    def _get_ohlcv_from_db(self, ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """TimescaleDB ohlcv_daily 테이블에서 조회."""
        try:
            query = """
                SELECT time, open, high, low, close, volume, trading_value, change_rate
                FROM ohlcv_daily
                WHERE ticker_code = %s AND time >= %s AND time <= %s
                ORDER BY time ASC
            """
            rows = self.db.fetch_all(query, (ticker, start, end))
            if not rows:
                return None

            df = pd.DataFrame(rows, columns=[
                'time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'trading_value', 'change_rate'
            ])
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)

            # 숫자형 변환
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            return df

        except Exception as e:
            logger.debug(f"[MarketData] DB OHLCV query failed for {ticker}: {e}")
            return None

    @staticmethod
    def _get_ohlcv_from_fdr(ticker: str, start: str, end: str) -> pd.DataFrame:
        """FDR에서 OHLCV 조회 (fallback)."""
        try:
            df = fdr.DataReader(ticker, start, end)
            if df.empty:
                logger.warning(f"[MarketData] Empty OHLCV from FDR for {ticker}")
            return df
        except Exception as e:
            logger.error(f"[MarketData] FDR OHLCV fetch failed for {ticker}: {e}")
            return pd.DataFrame()

    # ═════════════════════════════════════════════
    # Investor Trading (TimescaleDB → KIS fallback)
    # ═════════════════════════════════════════════

    def get_investor_trading(self, ticker: str, days: int = 30) -> pd.DataFrame:
        """
        종목별 투자자 매매동향 (외국인/기관/개인).
        TimescaleDB investor_trading 우선 → KIS API fallback.
        """
        df = self._get_investor_from_db(ticker, days)
        if df is not None and not df.empty:
            return df

        # Fallback: KIS API
        logger.debug(f"[MarketData] DB miss for investor data {ticker}, falling back to KIS")
        return self._get_investor_from_kis(ticker)

    def _get_investor_from_db(self, ticker: str, days: int = 30) -> Optional[pd.DataFrame]:
        """TimescaleDB investor_trading 테이블에서 조회."""
        try:
            query = """
                SELECT time, foreigner_net_qty, institution_net_qty, individual_net_qty,
                       foreigner_net_amt, institution_net_amt, individual_net_amt
                FROM investor_trading
                WHERE ticker_code = %s AND time >= NOW() - INTERVAL '%s days'
                ORDER BY time ASC
            """
            rows = self.db.fetch_all(query, (ticker, days))
            if not rows:
                return None

            df = pd.DataFrame(rows, columns=[
                'Date', 'foreigner_net_qty', 'institution_net_qty', 'individual_net_qty',
                'foreigner_net_amt', 'institution_net_amt', 'individual_net_amt'
            ])
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)

            for col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            return df

        except Exception as e:
            logger.debug(f"[MarketData] DB investor query failed for {ticker}: {e}")
            return None

    def _get_investor_from_kis(self, ticker: str) -> pd.DataFrame:
        """KIS API에서 투자자 매매동향 조회 (fallback)."""
        if not self.kis.is_configured:
            logger.warning("[MarketData] KIS API key not configured → no investor data")
            return pd.DataFrame()
        try:
            return self.kis.get_investor_trading(ticker)
        except Exception as e:
            logger.error(f"[MarketData] KIS investor trading failed for {ticker}: {e}")
            return pd.DataFrame()

    # ═════════════════════════════════════════════
    # Sector Index (TimescaleDB → KIS/FDR fallback)
    # ═════════════════════════════════════════════

    def get_sector_daily(
        self, sector_code: str, start: str, end: str
    ) -> pd.DataFrame:
        """
        업종 기간별 시세. TimescaleDB sector_indices 우선 → KIS/FDR fallback.
        """
        df = self._get_sector_from_db(sector_code, start, end)
        if df is not None and not df.empty and len(df) >= 5:
            return df

        # Fallback: KIS API → FDR
        return self._get_sector_from_api(sector_code, start, end)

    def _get_sector_from_db(self, sector_code: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """TimescaleDB sector_indices에서 조회."""
        try:
            query = """
                SELECT time, close, change_rate
                FROM sector_indices
                WHERE sector_code = %s AND time >= %s AND time <= %s
                ORDER BY time ASC
            """
            rows = self.db.fetch_all(query, (sector_code, start, end))
            if not rows:
                return None

            df = pd.DataFrame(rows, columns=['time', 'Close', 'change_rate'])
            df['time'] = pd.to_datetime(df['time'])
            df.set_index('time', inplace=True)
            df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
            return df

        except Exception as e:
            logger.debug(f"[MarketData] DB sector query failed for {sector_code}: {e}")
            return None

    def _get_sector_from_api(self, sector_code: str, start: str, end: str) -> pd.DataFrame:
        """KIS API / FDR fallback."""
        if self.kis.is_configured:
            try:
                df = self.kis.get_sector_daily(sector_code, start, end)
                if not df.empty:
                    return df
            except Exception as e:
                logger.warning(f"[MarketData] KIS sector daily failed: {e}")

        try:
            return fdr.DataReader(sector_code, start, end)
        except Exception:
            return pd.DataFrame()

    # ═════════════════════════════════════════════
    # Index Data (FDR — TimescaleDB에 별도 저장 없음)
    # ═════════════════════════════════════════════

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

    # ═════════════════════════════════════════════
    # V-KOSPI (FDR)
    # ═════════════════════════════════════════════

    @staticmethod
    def get_vkospi(start: str, end: str) -> pd.DataFrame:
        """V-KOSPI (KOSPI 200 변동성 지수). FDR DataReader 사용."""
        try:
            # VKOSPI fetch is currently failing (Yellow/FDR issue). Fail fast.
            # return fdr.DataReader("VKOSPI", start, end)
            return pd.DataFrame()
        except Exception as e:
            logger.warning(f"[MarketData] V-KOSPI fetch failed: {e}")
            return pd.DataFrame()

    # ═════════════════════════════════════════════
    # Market Breadth (ADR)
    # ═════════════════════════════════════════════

    @staticmethod
    def get_advancing_declining(market: str = "KOSPI") -> Tuple[int, int]:
        """상승/하락 종목 수 반환. ADR 계산용. FDR StockListing."""
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

    # ═════════════════════════════════════════════
    # Batch OHLCV for Multiple Tickers (TimescaleDB)
    # ═════════════════════════════════════════════

    def get_ohlcv_batch(self, tickers: List[str], start: str, end: str) -> dict:
        """
        여러 종목의 OHLCV를 한 번에 조회 (TimescaleDB).
        Returns: {ticker_code: DataFrame}
        """
        try:
            placeholders = ','.join(['%s'] * len(tickers))
            query = f"""
                SELECT time, ticker_code, open, high, low, close, volume, trading_value
                FROM ohlcv_daily
                WHERE ticker_code IN ({placeholders})
                  AND time >= %s AND time <= %s
                ORDER BY ticker_code, time ASC
            """
            params = tuple(tickers) + (start, end)
            rows = self.db.fetch_all(query, params)

            if not rows:
                return {}

            df_all = pd.DataFrame(rows, columns=[
                'time', 'ticker_code', 'Open', 'High', 'Low', 'Close', 'Volume', 'trading_value'
            ])
            df_all['time'] = pd.to_datetime(df_all['time'])
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df_all[col] = pd.to_numeric(df_all[col], errors='coerce')

            result = {}
            for ticker, group in df_all.groupby('ticker_code'):
                g = group.set_index('time').drop(columns=['ticker_code'])
                result[ticker] = g

            return result

        except Exception as e:
            logger.error(f"[MarketData] Batch OHLCV query failed: {e}")
            return {}

    # ═════════════════════════════════════════════
    # KIS API Direct Access (특정 실시간 데이터)
    # ═════════════════════════════════════════════

    def get_program_trading(self, ticker: str) -> dict:
        """프로그램 매매 (비차익/차익). KIS API."""
        if not self.kis.is_configured:
            return {}
        try:
            return self.kis.get_program_trading(ticker)
        except Exception as e:
            logger.error(f"[MarketData] Program trading failed for {ticker}: {e}")
            return {}

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

    def get_stock_info(self, ticker: str) -> dict:
        """종목 기본 정보 (PER, PBR, EPS, 시총, 거래대금 등). KIS API."""
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

    # ═════════════════════════════════════════════
    # Active Tickers from DB
    # ═════════════════════════════════════════════

    def get_active_tickers(self, market: str = None) -> List[Dict]:
        """DB에서 활성 종목 리스트 조회."""
        try:
            if market:
                query = """
                    SELECT ticker_code, ticker_name, market_type, sector_code
                    FROM tickers
                    WHERE is_active = TRUE AND market_type = %s
                    ORDER BY ticker_code
                """
                rows = self.db.fetch_all(query, (market,))
            else:
                query = """
                    SELECT ticker_code, ticker_name, market_type, sector_code
                    FROM tickers
                    WHERE is_active = TRUE
                    ORDER BY ticker_code
                """
                rows = self.db.fetch_all(query)

            return [
                {"ticker_code": r[0], "ticker_name": r[1],
                 "market_type": r[2], "sector_code": r[3]}
                for r in rows
            ] if rows else []

        except Exception as e:
            logger.error(f"[MarketData] get_active_tickers failed: {e}")
            return []

    @staticmethod
    def get_stock_listing(market: str = "KOSPI") -> pd.DataFrame:
        """전 종목 스냅샷. FDR StockListing 사용."""
        try:
            return fdr.StockListing(market)
        except Exception as e:
            logger.error(f"[MarketData] StockListing failed: {e}")
            return pd.DataFrame()
