"""
Financial Data Collector
========================
Fetches financial statements from KIS API and stores them in the DB.
Run daily or weekly.
"""
import logging
import time
from typing import List, Dict, Any, Optional
from ..infrastructure.data_providers.kis_client import KISClient
from ..infrastructure.repositories.financial_repository import financial_repo
from ..infrastructure.data_providers.market_data import MarketDataProvider

logger = logging.getLogger(__name__)

class FinancialCollector:
    def __init__(self):
        self.kis = KISClient()
        self.repo = financial_repo
        self.market_data = MarketDataProvider(self.kis)

    def collect_all(self):
        """Collect financials for all active tickers."""
        tickers = self.market_data.get_active_tickers()
        if not tickers:
            logger.warning("[FinancialCollector] No active tickers found in DB. Trying fallback...")
            # Fallback to fetching Kospi/Kosdaq listing if DB is empty
            df_kospi = self.market_data.get_stock_listing("KOSPI")
            df_kosdaq = self.market_data.get_stock_listing("KOSDAQ")
            
            ticker_list = []
            if not df_kospi.empty:
                ticker_list.extend(df_kospi['Code'].tolist())
            if not df_kosdaq.empty:
                ticker_list.extend(df_kosdaq['Code'].tolist())
                
            # Remove duplicates
            ticker_list = list(set(ticker_list))
        else:
            ticker_list = [t['ticker_code'] for t in tickers]
            
        logger.info(f"[FinancialCollector] Starting collection for {len(ticker_list)} tickers.")
        
        success_count = 0
        fail_count = 0
        
        for i, ticker in enumerate(ticker_list):
            try:
                self.collect(ticker)
                success_count += 1
            except Exception as e:
                logger.error(f"[FinancialCollector] Failed for {ticker}: {e}")
                fail_count += 1
            
            # API Rate Limit Guard (KIS: ~20 req/sec technically, but safe buffer)
            time.sleep(0.5) 
            
            if (i + 1) % 50 == 0:
                logger.info(f"[FinancialCollector] Progress: {i+1}/{len(ticker_list)}")

        logger.info(f"[FinancialCollector] Completed. Success: {success_count}, Failed: {fail_count}")

    def collect(self, ticker: str):
        """Fetch and save financials for a single ticker."""
        # 1. Get Stock Info (for PER, EPS etc)
        stock_info = self.kis.get_stock_info(ticker)
        
        # 2. Get Financial Statements (Try KIS first)
        fin_data = self.kis.get_financial_statements(ticker) # Returns list of dicts
        
        saved_count = 0
        
        # 3a. Process KIS Data
        if fin_data and isinstance(fin_data, list):
            for item in fin_data:
                mapped = self._map_kis_response(ticker, item, stock_info)
                if mapped:
                    self.repo.save_financial_statement(ticker, mapped)
                    saved_count += 1
        
        # 3b. Fallback: Naver Finance Crawler (if KIS failed)
        if saved_count == 0:
            # logger.info(f"[FinancialCollector] KIS failed for {ticker}. Trying Naver Fallback...")
            from ..infrastructure.crawlers.naver_finance import NaverFinanceCrawler
            crawler = NaverFinanceCrawler()
            naver_data = crawler.get_financials(ticker)
            
            for item in naver_data:
                self.repo.save_financial_statement(ticker, item)
                saved_count += 1
                
            if saved_count > 0:
                logger.info(f"[FinancialCollector] Saved {saved_count} records for {ticker} via Naver.")
            else:
                pass 
                # logger.warning(f"[FinancialCollector] No financials found for {ticker} (KIS & Naver)")

    def _map_kis_response(self, ticker: str, item: Dict[str, Any], stock_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Map KIS API response item to DB schema dict."""
        period_raw = item.get("stac_yymm") # e.g. "202312"
        if not period_raw:
            return None
            
        # Format period code: "202312" -> "2023.12"
        period_code = f"{period_raw[:4]}.{period_raw[4:]}"
        
        # Determine report type (quarter vs annual) if possible
        # KIS sometimes gives "bsop_prti_tpl_nm" (Business Period Template Name): "년", "분기"
        report_type_nm = item.get("bsop_prti_tpl_nm", "")
        report_type = "Annual" if "년" in report_type_nm else "Quarterly"

        def to_int(val):
            try: return int(float(str(val).replace(',', '')))
            except: return 0
            
        def to_float(val):
            try: return float(str(val).replace(',', ''))
            except: return 0.0

        # Mapping
        # Note: KIS field names are tricky (e.g. stac_yymm, crs_asst_tot_amt)
        # Assuming standard output keys. If keys differ, need adjustment.
        # Based on typical KIS response for 'inquire-financial-statement':
        
        data = {
            'period_code': period_code,
            'report_type': report_type,
            
            'total_assets': to_int(item.get("total_assets") or item.get("total_asset_amt")),
            'total_liabilities': to_int(item.get("total_liabilities") or item.get("total_liab_amt")), 
            'total_equity': to_int(item.get("total_equity") or item.get("total_cptl_amt")),
            'current_assets': to_int(item.get("current_assets") or item.get("crs_asst_tot_amt")),
            'current_liabilities': to_int(item.get("current_liabilities") or item.get("crs_liab_tot_amt")),
            
            'revenue': to_int(item.get("revenue") or item.get("sale_account")),
            'operating_income': to_int(item.get("operating_income") or item.get("bsop_prti")), 
            'net_income': to_int(item.get("net_income") or item.get("thtr_ntin")),
            'gross_profit': to_int(item.get("gross_profit") or item.get("gros_prof")),
            
            # This field might vary in name
            'operating_cash_flow': to_int(item.get("operating_cash_flow") or item.get("cf_op_activity")), 
            
            'total_shares': to_int(item.get("total_stock_cnt")),
            
            # Ratios
            'eps': to_float(item.get("eps")),
            'bps': to_float(item.get("bps")),
            'roa': to_float(item.get("roa")),
            'roe': to_float(item.get("roe")),
            
            'gross_margin': to_float(item.get("gross_profit_margin")),
            'operating_margin': to_float(item.get("operating_profit_margin")),
            'net_margin': to_float(item.get("net_profit_margin")),
            
            'current_ratio': to_float(item.get("current_ratio")),
            'debt_ratio': to_float(item.get("debt_ratio") or item.get("liab_ratio")),
            'asset_turnover': to_float(item.get("total_asset_turnover_ratio")),
        }
        
        # If stock info matches this period (likely current), fill in missing PER etc.
        # But stock_info is usually "current", financials are "historical".
        # We can store current stock info PER in the latest financial record if needed,
        # but better to calculate or trust the item fields if present.
        
        return data

if __name__ == "__main__":
    # Test run
    collector = FinancialCollector()
    collector.collect_all()
