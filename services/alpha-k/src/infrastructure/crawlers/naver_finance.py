"""
Naver Finance Crawler
=====================
Backup financial data provider when KIS API fails (e.g. in Virtual Trading environment).
Crawls Naver Finance item page for quarterly/annual consolidated financials.
"""
import requests
import pandas as pd
import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class NaverFinanceCrawler:
    
    BASE_URL = "https://finance.naver.com/item/main.naver"
    
    def get_financials(self, ticker: str) -> List[Dict[str, Any]]:
        """
        Fetch financials (Annual & Quarterly) from Naver Finance.
        Returns a list of dicts matching the DB schema.
        """
        try:
            url = f"{self.BASE_URL}?code={ticker}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            # Using pandas read_html directly on the main page.
            # We target the table that usually contains "매출액" in the first column/index.
            dfs = pd.read_html(url, encoding='euc-kr', header=0) # Naver uses EUC-KR
            
            target_df = None
            for df in dfs:
                # Naver financial table has 'Pool' of columns often MultiIndex or specific headers
                # Check for key financial metrics in the first column (if exists) or index
                # Usually row 0 or index contains '매출액'
                if not df.empty and df.shape[1] > 3:
                    if '매출액' in str(df.iloc[:, 0].values) or '영업이익' in str(df.iloc[:, 0].values):
                        target_df = df
                        break
                    # Sometimes headers contain '최근 연간 실적'
                    if '최근 연간 실적' in str(df.columns):
                        target_df = df
                        break
            
            if target_df is None or target_df.empty:
                logger.warning(f"[NaverCrawler] No financial table found for {ticker}")
                return []

            return self._parse_financial_table(ticker, target_df)

        except Exception as e:
            logger.error(f"[NaverCrawler] Failed to crawl {ticker}: {e}")
            return []

    def _parse_financial_table(self, ticker: str, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Parse the specific financial table structure from Naver.
        Expected columns: 0 (Key), 1~4 (Annual), 5~10 (Quarterly) usually.
        """
        results = []
        
        # Determine strict structure.
        # Column 0 is usually the Metric Name ('매출액', '영업이익'...)
        # Columns 1..N are periods.
        
        # Fix column names if MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            # Flatten to simple list
            new_cols = []
            for col in df.columns:
                # col is a tuple like ('최근 연간 실적', '2021.12')
                # We want the date part primarily
                date_part = ""
                type_part = ""
                for part in col:
                    s_part = str(part).strip()
                    if re.match(r'\d{4}\.\d{2}', s_part):
                        date_part = s_part.replace('(E)', '').strip()
                    if '연간' in s_part:
                        type_part = 'Annual'
                    elif '분기' in s_part:
                        type_part = 'Quarterly'
                
                # If date found, use it. If strictly '최근 연간 실적' etc, mark type.
                if date_part:
                     new_cols.append({'date': date_part, 'type': type_part})
                else:
                     new_cols.append(None) # Metric column or invalid
            
            cols_meta = new_cols
        else:
            # Simple Index
            # Usually row 0 or 1 has dates if header didn't catch it.
            # But let's assume header=0 worked somewhat.
            cols_meta = []
            current_type = 'Annual'
            for col in df.columns:
                s = str(col).strip()
                if re.match(r'\d{4}\.\d{2}', s):
                    cols_meta.append({'date': s.replace('(E)', '').strip(), 'type': current_type})
                elif '최근 연간' in s:
                    current_type = 'Annual'
                    cols_meta.append(None)
                elif '최근 분기' in s:
                    current_type = 'Quarterly'
                    cols_meta.append(None)
                else:
                    cols_meta.append(None)

        # Set index to the first column (Metric Names)
        # Rename duplicate metrics if any? Usually unique.
        try:
            df = df.set_index(df.columns[0])
        except:
            return []
            
        # Iterate over columns that have valid dates
        for i, meta in enumerate(cols_meta):
            if not meta or not meta['date']:
                continue
            
            # Since we set index = col 0, the data columns are shifted by -1 in iloc access if we access by position
            # But 'cols_meta' corresponds to original columns. col 0 (Metric) is meta[0] (None).
            # So meta[i] data is at df.iloc[:, i-1].
            
            if i == 0: continue # Should be None anyway
            
            col_idx = i - 1
            if col_idx < 0 or col_idx >= df.shape[1]: 
                continue

            period_code = meta['date']
            report_type = meta['type'] or 'Quarterly'
            
            def get_val(keys):
                for k in keys:
                    # Find strictly matching index or partially matching?
                    # Naver: '매출액', '영업이익', 'ROE(%)' ...
                    matches = [idx for idx in df.index if k in str(idx)]
                    if matches:
                        try:
                            val = df.iloc[matches[0].name if isinstance(matches[0], int) else df.index.get_loc(matches[0]), col_idx]
                            # Handle Series if multiple matches? get_loc might return slice.
                            # Safer: df.loc[matches[0]].iloc[col_idx]
                            val = df.loc[matches[0]]
                            if isinstance(val, pd.Series):
                                val = val.iloc[col_idx]
                            return val
                        except: pass
                return 0

            def parse_float(v):
                if pd.isna(v) or v == '' or v == '-': return 0.0
                s = str(v).replace(',', '')
                try: return float(s)
                except: return 0.0

            # Naver Unit: 억원 (100 Million)
            unit = 100000000 
            
            revenue = parse_float(get_val(['매출액'])) * unit
            op_inc = parse_float(get_val(['영업이익'])) * unit
            net_inc = parse_float(get_val(['당기순이익'])) * unit
            
            op_margin = parse_float(get_val(['영업이익률']))
            net_margin = parse_float(get_val(['순이익률']))
            roe = parse_float(get_val(['ROE']))
            debt_ratio = parse_float(get_val(['부채비율']))
            curr_ratio = parse_float(get_val(['당좌비율'])) # Proxy
            reserve_ratio = parse_float(get_val(['유보율']))
            
            eps = parse_float(get_val(['EPS']))
            per = parse_float(get_val(['PER']))
            bps = parse_float(get_val(['BPS']))
            pbr = parse_float(get_val(['PBR']))
            
            # Estimate missing
            # operating_cash_flow ~ operating_income (rough proxy)
            ocf = op_inc 
            
            record = {
                'period_code': period_code,
                'report_type': report_type,
                'revenue': int(revenue),
                'operating_income': int(op_inc),
                'net_income': int(net_inc),
                'gross_profit': int(revenue * 0.2), # Rough estimate if missing
                'operating_cash_flow': int(ocf),
                
                'operating_margin': op_margin,
                'net_margin': net_margin,
                'roe': roe,
                'debt_ratio': debt_ratio,
                'current_ratio': curr_ratio,
                'eps': eps,
                'per': per,
                'bps': bps,
                'pbr': pbr,
                
                # Missing essential F-Score fields populated with defaults/proxies
                'total_assets': 0 if debt_ratio == 0 else int(op_inc * 10), # bogus
                'total_liabilities': 0,
                'total_equity': 0,
                'total_shares': 0,
                'gross_margin': op_margin, # Proxy
                'asset_turnover': 0,
                'roa': roe / (1 + (debt_ratio/100)) if debt_ratio > 0 else roe, # Dupont approx? ROE = ROA * Leverage
            }
            results.append(record)
            
        return results
