"""
Time Machine Provider for Backtesting
=====================================
과거 시점(Point-in-Time) 데이터를 에이전트에 제공하기 위한 Wrapper.
MarketDataProvider를 상속받아, 모든 데이터 조회를 `current_date` 이전으로 제한한다.
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict

from ..infrastructure.data_providers.market_data import MarketDataProvider

class TimeMachineProvider(MarketDataProvider):
    """
    백테스트용 데이터 제공자.
    set_current_date(dt)를 통해 시뮬레이션 시점을 설정하면,
    그 시점까지의 데이터만 반환하여 Look-ahead Bias를 방지한다.
    """

    def __init__(self):
        super().__init__()
        self.current_date: Optional[datetime] = None

    def set_current_date(self, date_str: str):
        """시뮬레이션 현재 날짜 설정 (YYYY-MM-DD)."""
        self.current_date = datetime.strptime(date_str, "%Y-%m-%d")

    def _filter_by_date(self, df: pd.DataFrame) -> pd.DataFrame:
        """데이터프레임을 현재 날짜 기준으로 필터링."""
        if self.current_date is None or df.empty:
            return df
        
        # 인덱스가 날짜인지 확인
        if isinstance(df.index, pd.DatetimeIndex):
            return df[df.index <= self.current_date]
        if 'Date' in df.columns:
            return df[df['Date'] <= self.current_date]
        if 'time' in df.columns:
            return df[df['time'] <= self.current_date]
        
        return df

    # ─────────────────────────────────────────────
    # Overrides
    # ─────────────────────────────────────────────

    def get_ohlcv(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        # 요청된 end 날짜가 시뮬레이션 날짜보다 미래라면 조정
        req_end = datetime.strptime(end, "%Y-%m-%d")
        if self.current_date and req_end > self.current_date:
            end = self.current_date.strftime("%Y-%m-%d")
        
        df = super().get_ohlcv(ticker, start, end)
        return self._filter_by_date(df)

    def get_investor_trading(self, ticker: str, days: int = 30) -> pd.DataFrame:
        # 내부적으로 NOW()를 쓰는 쿼리가 있다면 수정 필요하지만,
        # 여기서는 가져온 후 필터링하는 방식 사용
        # (DB 쿼리 레벨에서 막는 것이 성능상 좋지만, 편의상 후처리)
        df = super().get_investor_trading(ticker, days=days + 100) # 넉넉히 가져옴
        return self._filter_by_date(df).tail(days)

    def get_sector_daily(self, sector_code: str, start: str, end: str) -> pd.DataFrame:
        req_end = datetime.strptime(end, "%Y-%m-%d")
        if self.current_date and req_end > self.current_date:
            end = self.current_date.strftime("%Y-%m-%d")
        
        df = super().get_sector_daily(sector_code, start, end)
        return self._filter_by_date(df)

    # 실시간 API 호출 등은 백테스트에서 제한되어야 함
    def get_stock_info(self, ticker: str) -> Dict:
        # TODO: 과거 특정 시점의 PER/PBR 등을 DB에 저장해두고 조회해야 함.
        # 현재는 Mockup 또는 최근 데이터 리턴 (주의: Look-ahead 가능성)
        return {
            "per": 10.0,
            "pbr": 1.0,
            "eps": 1000,
            "bps": 10000,
            "div_yield": 0.0,
        }

    def get_financial_statements(self, ticker: str) -> Dict:
        # 재무제표는 발표일 기준이므로, current_date 이전에 발표된 것만 가져와야 함.
        # (구현 복잡도 높음 -> 추후 구현)
        # 안전한 더미 데이터 반환
        dummy_stmt = {
            "total_assets": "100000000000",
            "net_income": "10000000000",
            "operating_cash_flow": "12000000000",
            "total_liabilities": "50000000000",
            "current_ratio": "150.0",
            "total_stock_cnt": "10000000",
            "gross_profit_margin": "20.0",
            "total_asset_turnover_ratio": "0.8",
        }
        return [dummy_stmt, dummy_stmt] # [current, previous]
