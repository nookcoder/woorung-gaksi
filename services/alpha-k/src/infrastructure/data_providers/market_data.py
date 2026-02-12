"""
Alpha-K Infrastructure: Market Data Provider
=============================================
FinanceDataReader + pykrx를 래핑하여 에이전트에 데이터를 공급한다.
"""
import pandas as pd
import numpy as np
import FinanceDataReader as fdr
from pykrx import stock
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """주가, 지수, 환율 데이터를 통합 제공한다."""

    # ───── Price Data (FinanceDataReader) ─────

    @staticmethod
    def get_ohlcv(ticker: str, start: str, end: str) -> pd.DataFrame:
        """종목 OHLCV 데이터를 가져온다."""
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
        """지수 데이터 (KOSPI, KOSDAQ 등) - FDR 사용"""
        try:
            return fdr.DataReader(index_code, start, end)
        except Exception as e:
            logger.error(f"[MarketData] Index fetch failed for {index_code}: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_vkospi(start: str, end: str) -> pd.DataFrame:
        """
        V-KOSPI (KOSPI 200 변동성 지수).
        1차: pykrx의 get_index_ohlcv_by_date (코드: 1004)
        2차 (fallback): FDR DataReader
        """
        try:
            start_fmt = start.replace("-", "")
            end_fmt = end.replace("-", "")
            df = stock.get_index_ohlcv_by_date(start_fmt, end_fmt, "1004")
            if not df.empty:
                rename_map = {}
                for col in df.columns:
                    if '종가' in str(col):
                        rename_map[col] = 'Close'
                    elif '시가' in str(col):
                        rename_map[col] = 'Open'
                    elif '고가' in str(col):
                        rename_map[col] = 'High'
                    elif '저가' in str(col):
                        rename_map[col] = 'Low'
                    elif '거래량' in str(col):
                        rename_map[col] = 'Volume'
                if rename_map:
                    df = df.rename(columns=rename_map)
                return df
        except Exception as e:
            logger.warning(f"[MarketData] pykrx V-KOSPI failed: {e}")

        # Fallback: FDR
        try:
            df = fdr.DataReader("VKOSPI", start, end)
            return df
        except Exception as e:
            logger.error(f"[MarketData] V-KOSPI fetch failed (all sources): {e}")
            return pd.DataFrame()

    @staticmethod
    def get_usd_krw(start: str, end: str) -> pd.DataFrame:
        """USD/KRW 환율 데이터"""
        try:
            return fdr.DataReader("USD/KRW", start, end)
        except Exception as e:
            logger.error(f"[MarketData] USD/KRW fetch failed: {e}")
            return pd.DataFrame()

    # ───── Market Breadth ─────

    @staticmethod
    def get_advancing_declining(date: str = None, market: str = "KOSPI") -> Tuple[int, int]:
        """
        상승/하락 종목 수를 반환한다. ADR 계산용.

        1차: fdr.StockListing (오늘 기준 스냅샷)
        2차: pykrx get_market_ohlcv_by_ticker
        """
        # Method 1: FDR StockListing (가장 안정적, 오늘 기준만)
        try:
            df = fdr.StockListing(market)
            if not df.empty:
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
            logger.warning(f"[MarketData] FDR StockListing ADR failed: {e}")

        # Method 2: pykrx fallback (과거 날짜용)
        try:
            if date:
                date_fmt = date.replace("-", "")
            else:
                date_fmt = datetime.now().strftime("%Y%m%d")

            df = stock.get_market_ohlcv_by_ticker(date_fmt, market=market)
            if not df.empty:
                if '등락률' in df.columns:
                    changes = df['등락률']
                else:
                    return 0, 0
                advancing = int((changes > 0).sum())
                declining = int((changes < 0).sum())
                return advancing, declining
        except Exception as e:
            logger.warning(f"[MarketData] pykrx ADR fallback failed: {e}")

        return 0, 0

    @staticmethod
    def get_advancing_declining_history(days: int = 30, market: str = "KOSPI") -> pd.DataFrame:
        """
        n일간의 ADR 히스토리를 반환한다.
        KOSPI 지수 구성 종목의 일별 등락률로부터 계산.
        pykrx를 사용할 수 없는 경우 FDR StockListing 스냅샷을 반환.
        """
        try:
            end = datetime.now()
            start = end - timedelta(days=days * 2)  # 여유 있게 과거 데이터 확보

            # KOSPI 지수 데이터로 거래일 목록 확보
            kospi_df = fdr.DataReader("KS11", start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
            if kospi_df.empty or len(kospi_df) < days:
                return pd.DataFrame()

            trading_dates = kospi_df.index[-days:]
            records = []
            for dt in trading_dates:
                date_str = dt.strftime("%Y%m%d")
                try:
                    df = stock.get_market_ohlcv_by_ticker(date_str, market=market)
                    if not df.empty and '등락률' in df.columns:
                        adv = int((df['등락률'] > 0).sum())
                        dec = int((df['등락률'] < 0).sum())
                        adr = (adv / max(dec, 1)) * 100
                        records.append({"date": dt, "advancing": adv, "declining": dec, "adr": adr})
                except Exception:
                    continue

            if records:
                return pd.DataFrame(records).set_index("date")
            return pd.DataFrame()

        except Exception as e:
            logger.error(f"[MarketData] ADR history failed: {e}")
            return pd.DataFrame()

    # ───── Sector Data (pykrx) ─────

    @staticmethod
    def get_sector_list(market: str = "KOSPI") -> pd.DataFrame:
        """업종(섹터) 목록을 가져온다."""
        try:
            date = datetime.now().strftime("%Y%m%d")
            return stock.get_index_ticker_list(date, market)
        except Exception as e:
            logger.error(f"[MarketData] Sector list failed: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_sector_ohlcv(sector_code: str, start: str, end: str) -> pd.DataFrame:
        """특정 업종 지수 OHLCV"""
        try:
            start_fmt = start.replace("-", "")
            end_fmt = end.replace("-", "")
            return stock.get_index_ohlcv_by_date(start_fmt, end_fmt, sector_code)
        except Exception as e:
            logger.error(f"[MarketData] Sector OHLCV failed for {sector_code}: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_sector_tickers(sector_code: str, date: str = None) -> List[str]:
        """특정 업종에 속한 종목 코드 목록"""
        try:
            if date is None:
                date = datetime.now().strftime("%Y%m%d")
            else:
                date = date.replace("-", "")
            return stock.get_index_portfolio_deposit_file(sector_code, date)
        except Exception as e:
            logger.error(f"[MarketData] Sector tickers failed for {sector_code}: {e}")
            return []

    # ───── Investor/Supply-Demand Data (pykrx) ─────

    @staticmethod
    def get_investor_trading_value(ticker: str, start: str, end: str) -> pd.DataFrame:
        """
        투자자별 거래대금 (기관, 외국인, 개인).
        pykrx의 get_market_trading_value_by_date 사용.
        """
        try:
            start_fmt = start.replace("-", "")
            end_fmt = end.replace("-", "")
            df = stock.get_market_trading_value_by_date(start_fmt, end_fmt, ticker)
            if not df.empty:
                col_map = {}
                for col in df.columns:
                    col_str = str(col)
                    if '기관' in col_str and '합계' in col_str:
                        col_map[col] = 'institution'
                    elif '기타법인' in col_str:
                        col_map[col] = 'corp_other'
                    elif '개인' in col_str:
                        col_map[col] = 'individual'
                    elif '외국인' in col_str and '합계' in col_str:
                        col_map[col] = 'foreigner'
                    elif '전체' in col_str:
                        col_map[col] = 'total'
                if col_map:
                    df = df.rename(columns=col_map)
            return df
        except Exception as e:
            logger.error(f"[MarketData] Investor data failed for {ticker}: {e}")
            return pd.DataFrame()

    @staticmethod
    def get_market_cap(ticker: str, date: str = None) -> int:
        """종목 시가총액 (원)"""
        try:
            if date is None:
                date = datetime.now().strftime("%Y%m%d")
            else:
                date = date.replace("-", "")
            df = stock.get_market_cap_by_date(date, date, ticker)
            if not df.empty and '시가총액' in df.columns:
                return int(df['시가총액'].iloc[-1])
            return 0
        except Exception as e:
            logger.error(f"[MarketData] Market cap failed for {ticker}: {e}")
            return 0

    @staticmethod
    def get_trading_value(ticker: str, date: str = None) -> int:
        """종목 거래대금 (원)"""
        try:
            if date is None:
                date = datetime.now().strftime("%Y%m%d")
            else:
                date = date.replace("-", "")
            df = stock.get_market_cap_by_date(date, date, ticker)
            if not df.empty and '거래대금' in df.columns:
                return int(df['거래대금'].iloc[-1])
            return 0
        except Exception as e:
            logger.error(f"[MarketData] Trading value failed for {ticker}: {e}")
            return 0

    # ───── Fundamental Data (pykrx) ─────

    @staticmethod
    def get_fundamental(ticker: str, start: str, end: str) -> pd.DataFrame:
        """PER, PBR, EPS, BPS 등 기본 밸류에이션 지표"""
        try:
            start_fmt = start.replace("-", "")
            end_fmt = end.replace("-", "")
            return stock.get_market_fundamental_by_date(start_fmt, end_fmt, ticker)
        except Exception as e:
            logger.error(f"[MarketData] Fundamental failed for {ticker}: {e}")
            return pd.DataFrame()
