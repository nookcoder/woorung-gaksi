"""
Financial Statement Repository
==============================
Handles database operations for financial data.
"""
import logging
from typing import List, Dict, Optional, Any
from ..db.db_client import db_client

logger = logging.getLogger(__name__)

class FinancialRepository:
    def __init__(self, db=None):
        self.db = db or db_client

    def save_financial_statement(self, ticker: str, data: Dict[str, Any]):
        """
        Upsert a financial statement record.
        Args:
            ticker: Stock ticker
            data: Dictionary containing fields from the financial_statements table schema
                  e.g. {'period_code': '2023.12', 'total_assets': ..., ...}
        """
        if not data.get('period_code'):
            logger.warning(f"Missing period_code for {ticker}, skipping save.")
            return

        query = """
        INSERT INTO financial_statements (
            ticker_code, period_code, report_type,
            total_assets, total_liabilities, total_equity,
            current_assets, current_liabilities,
            revenue, operating_income, net_income, gross_profit,
            operating_cash_flow, total_shares,
            eps, bps, gross_margin, operating_margin, net_margin,
            roa, roe, current_ratio, debt_ratio, asset_turnover,
            updated_at
        ) VALUES (
            %(ticker)s, %(period)s, %(report_type)s,
            %(assets)s, %(libs)s, %(equity)s,
            %(curr_assets)s, %(curr_libs)s,
            %(revenue)s, %(op_inc)s, %(net_inc)s, %(gross_profit)s,
            %(ocf)s, %(shares)s,
            %(eps)s, %(bps)s, %(gm)s, %(om)s, %(nm)s,
            %(roa)s, %(roe)s, %(curr_ratio)s, %(debt_ratio)s, %(asset_turnover)s,
            NOW()
        )
        ON CONFLICT (ticker_code, period_code, report_type) 
        DO UPDATE SET
            total_assets = EXCLUDED.total_assets,
            total_liabilities = EXCLUDED.total_liabilities,
            total_equity = EXCLUDED.total_equity,
            current_assets = EXCLUDED.current_assets,
            current_liabilities = EXCLUDED.current_liabilities,
            revenue = EXCLUDED.revenue,
            operating_income = EXCLUDED.operating_income,
            net_income = EXCLUDED.net_income,
            gross_profit = EXCLUDED.gross_profit,
            operating_cash_flow = EXCLUDED.operating_cash_flow,
            total_shares = EXCLUDED.total_shares,
            eps = EXCLUDED.eps,
            bps = EXCLUDED.bps,
            gross_margin = EXCLUDED.gross_margin,
            operating_margin = EXCLUDED.operating_margin,
            net_margin = EXCLUDED.net_margin,
            roa = EXCLUDED.roa,
            roe = EXCLUDED.roe,
            current_ratio = EXCLUDED.current_ratio,
            debt_ratio = EXCLUDED.debt_ratio,
            asset_turnover = EXCLUDED.asset_turnover,
            updated_at = NOW();
        """
        
        params = {
            'ticker': ticker,
            'period': data.get('period_code'),
            'report_type': data.get('report_type', 'Quarterly'),
            'assets': data.get('total_assets'),
            'libs': data.get('total_liabilities'),
            'equity': data.get('total_equity'),
            'curr_assets': data.get('current_assets'),
            'curr_libs': data.get('current_liabilities'),
            'revenue': data.get('revenue'),
            'op_inc': data.get('operating_income'),
            'net_inc': data.get('net_income'),
            'gross_profit': data.get('gross_profit'),
            'ocf': data.get('operating_cash_flow'),
            'shares': data.get('total_shares'),
            'eps': data.get('eps'),
            'bps': data.get('bps'),
            'gm': data.get('gross_margin'),
            'om': data.get('operating_margin'),
            'nm': data.get('net_margin'),
            'roa': data.get('roa'),
            'roe': data.get('roe'),
            'curr_ratio': data.get('current_ratio'),
            'debt_ratio': data.get('debt_ratio'),
            'asset_turnover': data.get('asset_turnover'),
        }
        
        try:
            self.db.execute(query, params)
        except Exception as e:
            logger.error(f"[FinancialRepo] Save failed for {ticker}-{data.get('period_code')}: {e}")

    def get_latest_financials(self, ticker: str, report_type='Quarterly', limit=2) -> List[Dict]:
        """
        Get latest N financial statements for a ticker.
        """
        query = """
        SELECT 
            period_code, total_assets, total_liabilities, total_equity,
            current_assets, current_liabilities,
            revenue, operating_income, net_income, gross_profit,
            operating_cash_flow, total_shares,
            eps, bps, gross_margin, operating_margin, net_margin,
            roa, roe, current_ratio, debt_ratio, asset_turnover
        FROM financial_statements
        WHERE ticker_code = %s AND report_type = %s
        ORDER BY period_code DESC
        LIMIT %s
        """
        
        rows = self.db.fetch_all(query, (ticker, report_type, limit))
        
        results = []
        keys = [
            'period_code', 'total_assets', 'total_liabilities', 'total_equity',
            'current_assets', 'current_liabilities',
            'revenue', 'operating_income', 'net_income', 'gross_profit',
            'operating_cash_flow', 'total_shares',
            'eps', 'bps', 'gross_margin', 'operating_margin', 'net_margin',
            'roa', 'roe', 'current_ratio', 'debt_ratio', 'asset_turnover'
        ]
        
        for row in rows:
            results.append(dict(zip(keys, row)))
            
        return results

financial_repo = FinancialRepository()
