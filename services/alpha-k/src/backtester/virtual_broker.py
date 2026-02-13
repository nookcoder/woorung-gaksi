"""
Virtual Broker for Backtesting
==============================
에이전트의 매매 계획(TradePlan)을 실제 주문처럼 처리하고 자산을 관리한다.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd

from ..domain.models import TradePlan

@dataclass
class Position:
    ticker: str
    shares: int
    entry_price: float
    entry_date: str
    current_price: float = 0.0
    stop_loss: float = 0.0
    target_price: float = 0.0
    pyramiding_level: int = 0
    max_price: float = 0.0 # Trailing Stop용

@dataclass
class TradeRecord:
    ticker: str
    direction: str
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    exit_reason: str

class VirtualBroker:
    def __init__(self, initial_capital: float = 100_000_000):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {} # ticker -> Position
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[Dict] = []
        
        # 수수료/세금
        self.commission_rate = 0.00015
        self.tax_rate = 0.0023
        self.slippage_rate = 0.001

    @property
    def total_equity(self) -> float:
        pos_value = sum(p.shares * p.current_price for p in self.positions.values())
        return self.cash + pos_value

    def submit_plan(self, plan: TradePlan, current_date: str):
        """
        RiskAgent가 생성한 TradePlan을 접수한다.
        이미 포지션이 있으면 피라미딩 여부 확인.
        없으면 신규 진입 대기.
        """
        if not plan.is_actionable:
            return

        if plan.ticker in self.positions:
            # TODO: Pyramiding logic
            pass
        else:
            # 신규 진입 (다음날 시가/조건부 진입 가정)
            # 여기서는 단순히 다음날 시가(Open)에 진입한다고 가정하거나,
            # Limit Order로 관리해야 함. 편의상 'Market on Open'으로 처리.
            self._enter_position(plan, current_date)

    def _enter_position(self, plan: TradePlan, date: str):
        # 자금 관리: 1차 진입 물량만큼 매수
        cost = plan.entry_zone * plan.position_size_shares
        commission = cost * self.commission_rate
        
        if self.cash >= (cost + commission):
            self.cash -= (cost + commission)
            self.positions[plan.ticker] = Position(
                ticker=plan.ticker,
                shares=plan.position_size_shares,
                entry_price=plan.entry_zone, # 실제 체결가는 process_market_data에서 결정될 수도 있음
                entry_date=date,
                current_price=plan.entry_zone,
                stop_loss=plan.stop_loss,
                target_price=plan.target_price,
                max_price=plan.entry_zone
            )
            print(f"[{date}] BUY {plan.ticker}: {plan.position_size_shares} shares @ {plan.entry_zone:,.0f}")

    def process_market_data(self, date: str, market_data: Dict[str, pd.Series]):
        """
        하루치 시장 데이터(OHLCV)를 받아 포지션을 업데이트하고 청산 조건을 확인한다.
        market_data: {ticker: Series(Open, High, Low, Close...)}
        """
        for ticker, pos in list(self.positions.items()):
            if ticker not in market_data:
                continue
            
            row = market_data[ticker]
            curr_price = row['Close']
            high = row['High']
            low = row['Low']
            
            # Update position
            pos.current_price = curr_price
            pos.max_price = max(pos.max_price, high)
            
            # Check Stop Loss
            if low <= pos.stop_loss:
                self._exit_position(ticker, pos.stop_loss, date, "STOP_LOSS")
                continue

            # Check Target
            if high >= pos.target_price:
                self._exit_position(ticker, pos.target_price, date, "TARGET")
                continue
            
            # Trailing Stop (ATR 기반 등) - 여기서는 간소화
            # RiskAgent가 매일 새로운 Plan을 주면 업데이트 가능.

        # Equity Logging
        self.equity_curve.append({
            "date": date,
            "equity": self.total_equity,
            "cash": self.cash
        })

    def _exit_position(self, ticker: str, price: float, date: str, reason: str):
        pos = self.positions.pop(ticker)
        revenue = price * pos.shares
        commission = revenue * (self.commission_rate + self.tax_rate)
        
        self.cash += (revenue - commission)
        
        pnl = (price - pos.entry_price) * pos.shares - commission
        pnl_pct = (price / pos.entry_price - 1) * 100
        
        self.trades.append(TradeRecord(
            ticker=ticker,
            direction="LONG",
            entry_date=pos.entry_date,
            entry_price=pos.entry_price,
            exit_date=date,
            exit_price=price,
            shares=pos.shares,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=reason
        ))
        print(f"[{date}] SELL {ticker}: {pos.shares} shares @ {price:,.0f} ({reason}) PnL: {pnl:,.0f} ({pnl_pct:.2f}%)")

    def get_summary(self):
        return {
            "final_equity": self.total_equity,
            "total_return_pct": (self.total_equity / self.initial_capital - 1) * 100,
            "total_trades": len(self.trades),
            "win_rate": len([t for t in self.trades if t.pnl > 0]) / len(self.trades) * 100 if self.trades else 0
        }
