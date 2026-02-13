"""
Market Data Collector (KIS API)
===============================
KIS Open API를 사용하여 시장 데이터를 수집하고 TimescaleDB에 적재한다.

기능:
1. update_master(): 전 종목 리스트 갱신 (FDR 사용 → DB)
2. update_daily_ohlcv(): 활성 종목의 일봉 데이터 업데이트 (KIS API → DB)
3. update_sector_indices(): 업종별 지수 업데이트 (KIS API → DB)
"""
import time
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import List, Optional

import FinanceDataReader as fdr
from ..infrastructure.data_providers.kis_client import KISClient
from ..infrastructure.db.db_client import db_client

logger = logging.getLogger(__name__)

class MarketDataCollector:
    """시장 데이터 수집 및 DB 적재 클래스."""

    def __init__(self, kis_client: Optional[KISClient] = None):
        self.kis = kis_client or KISClient()
        self.db = db_client
        self.markets = ["KOSPI", "KOSDAQ"]
        
        # KIS API Rate Limit (초당 20건 제한 → 0.06s 대기)
        self.API_DELAY = 0.06

    def update_master(self):
        """
        1. 전 종목 리스트(Listing) 갱신.
        - FDR를 사용하여 KOSPI, KOSDAQ 종목 정보를 가져온다.
        - DB `tickers` 테이블에 UPSERT 한다.
        """
        logger.info("[Collector] Updating ticker master...")
        try:
            for market in self.markets:
                df = fdr.StockListing(market)
                if df.empty:
                    logger.warning(f"[Collector] FDR Listing empty for {market}")
                    continue

                # Batch Insert Query
                query = """
                INSERT INTO tickers (
                    ticker_code, ticker_name, market_type, sector_code, industry, listing_date, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (ticker_code) DO UPDATE SET
                    ticker_name = EXCLUDED.ticker_name,
                    industry = EXCLUDED.industry,
                    updated_at = NOW();
                """
                
                with self.db.get_cursor() as cur:
                    for _, row in df.iterrows():
                        try:
                            code = row['Code']
                            name = row['Name']
                            sector = row.get('Sector', '') # FDR 컬럼명 확인 필요
                            industry = row.get('Industry', '')
                            # ListingDate handling
                            listing_date = row.get('ListingDate')
                            if pd.isna(listing_date):
                                listing_date = None

                            cur.execute(query, (code, name, market, sector, industry, listing_date))
                        except Exception as e:
                            logger.error(f"[Collector] Failed to insert ticker {code}: {e}")
                            pass
                
                logger.info(f"[Collector] Updated {len(df)} tickers for {market}")

        except Exception as e:
            logger.error(f"[Collector] Master update failed: {e}")

    def update_daily_ohlcv_batch(self, limit: int = None):
        """
        2. 활성 종목의 일봉 데이터를 업데이트한다.
        - DB에서 활성 종목 리스트 조회
        - 각 종목별로 KIS API 호출 (최근 3일치만 갱신, 또는 전체)
        - Bulk Insert
        """
        logger.info("[Collector] Starting daily OHLCV update...")
        try:
            # 1. 활성 종목 조회
            active_tickers = self.db.fetch_all("SELECT ticker_code FROM tickers WHERE is_active = TRUE")
            if not active_tickers:
                logger.warning("[Collector] No active tickers found. Run update_master() first.")
                return

            tickers = [t[0] for t in active_tickers]
            if limit:
                tickers = tickers[:limit] # Test용

            logger.info(f"[Collector] Target: {len(tickers)} tickers")

            # 2. 날짜 범위 설정 (어제 ~ 오늘)
            # 수집기가 매일 돈다고 가정하면, D-1 ~ D-0 데이터만 채우면 됨.
            # 하지만 안전하게 D-7 ~ D-0 (중복은 TimescaleDB가 처리하거나 UPSERT)
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=5)
            start_str = start_dt.strftime("%Y%m%d")
            end_str = end_dt.strftime("%Y%m%d")

            success_count = 0
            
            for i, ticker in enumerate(tickers):
                try:
                    # KIS API Call
                    df = self.kis.get_daily_price(ticker, start_str, end_str) # Returns DF with Date index
                    time.sleep(self.API_DELAY)

                    if df.empty:
                        continue

                    # Bulk Insert
                    self._save_ohlcv(ticker, df)
                    success_count += 1
                    
                    if i % 100 == 0:
                        logger.info(f"[Collector] Processed {i}/{len(tickers)}...")

                except Exception as e:
                    logger.warning(f"[Collector] Failed {ticker}: {e}")
                    continue

            logger.info(f"[Collector] Completed OHLCV update. Success: {success_count}/{len(tickers)}")

        except Exception as e:
            logger.error(f"[Collector] Daily OHLCV update failed: {e}")

    def _save_ohlcv(self, ticker: str, df: pd.DataFrame):
        """DataFrame을 DB에 저장 (UPSERT)"""
        query = """
        INSERT INTO ohlcv_daily (
            time, ticker_code, open, high, low, close, volume, change_rate
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (time, ticker_code) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume,
            change_rate = EXCLUDED.change_rate;
        """
        
        with self.db.get_cursor() as cur:
            for date_idx, row in df.iterrows():
                # date_idx is Timestamp
                try:
                    cur.execute(query, (
                        date_idx, 
                        ticker, 
                        float(row['Open']), 
                        float(row['High']), 
                        float(row['Low']), 
                        float(row['Close']), 
                        int(row['Volume']),
                        float(row.get('Change', 0))
                    ))
                except Exception as e:
                    logger.error(f"[Collector] Row insert failed {ticker} {date_idx}: {e}")

# Entry Point for Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    collector = MarketDataCollector()
    collector.update_master()
    collector.update_daily_ohlcv_batch(limit=10) # Test with 10 tickers
