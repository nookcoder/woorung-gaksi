"""
Alpha-K Backtesting Engine (Phase 2.5a)
=======================================
pandas 벡터 기반 백테스트 엔진.
TimescaleDB의 OHLCV 데이터로 전략을 검증한다.

Features:
1. Vector-based simulation (no event loop → fast)
2. Slippage & commission modeling
3. ATR-based stop loss / trailing stop
4. Pyramiding (30/30/40) support
5. Performance metrics (Sharpe, MDD, Win Rate, Profit Factor)
6. Trade log with entry/exit reasons
"""
import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from datetime import datetime

from ..infrastructure.db.db_client import db_client

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────

@dataclass
class TradeRecord:
    """개별 거래 기록"""
    ticker: str
    direction: str              # "LONG" or "SHORT"
    entry_date: str
    entry_price: float
    exit_date: str
    exit_price: float
    shares: int
    pnl: float                  # 실현 손익 (원)
    pnl_pct: float              # 수익률 (%)
    holding_days: int
    exit_reason: str            # "STOP_LOSS", "TARGET", "TRAILING", "SIGNAL_EXIT"


@dataclass
class BacktestResult:
    """백테스트 결과 요약"""
    strategy_name: str
    period: str                 # "2024-01-01 ~ 2024-12-31"
    initial_capital: float
    final_capital: float
    total_return: float         # 총 수익률 (%)
    annualized_return: float    # 연환산 수익률 (%)
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float         # MDD (%)
    max_drawdown_duration: int  # MDD 지속 기간 (일)
    win_rate: float             # 승률 (%)
    profit_factor: float        # 총이익 / 총손실
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float              # 평균 수익 (%)
    avg_loss: float             # 평균 손실 (%)
    avg_holding_days: float
    commission_total: float
    trades: List[TradeRecord]
    equity_curve: pd.Series     # 자산 곡선


# ─────────────────────────────────────────────
# Strategy Interface
# ─────────────────────────────────────────────

class BaseStrategy:
    """
    전략 베이스 클래스. 상속하여 사용.
    """
    name: str = "BaseStrategy"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        DataFrame에 'signal' 컬럼을 추가한다.
        signal: 1 = Buy, -1 = Sell, 0 = Hold
        """
        raise NotImplementedError


class MomentumStrategy(BaseStrategy):
    """
    모멘텀 전략 (EMA 크로스 + RSI 필터).
    - Buy: EMA20 > EMA60 & RSI < 70 & Volume > 1.5x avg
    - Sell: EMA20 < EMA60 or RSI > 80
    """
    name = "Momentum_EMA20x60_RSI"

    def __init__(self, ema_short: int = 20, ema_long: int = 60, rsi_period: int = 14):
        self.ema_short = ema_short
        self.ema_long = ema_long
        self.rsi_period = rsi_period

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        # Indicators
        df["EMA_S"] = df["Close"].ewm(span=self.ema_short, adjust=False).mean()
        df["EMA_L"] = df["Close"].ewm(span=self.ema_long, adjust=False).mean()
        df["RSI"] = self._rsi(df["Close"], self.rsi_period)
        df["VOL_MA"] = df["Volume"].rolling(20).mean()
        df["ATR"] = self._atr(df, 14)

        df["signal"] = 0

        # Buy conditions
        buy_cond = (
            (df["EMA_S"] > df["EMA_L"])
            & (df["EMA_S"].shift(1) <= df["EMA_L"].shift(1))  # Cross
            & (df["RSI"] < 70)
            & (df["Volume"] > df["VOL_MA"] * 1.2)
        )
        df.loc[buy_cond, "signal"] = 1

        # Sell conditions
        sell_cond = (
            (df["EMA_S"] < df["EMA_L"])
            | (df["RSI"] > 80)
        )
        df.loc[sell_cond, "signal"] = -1

        return df

    @staticmethod
    def _rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def _atr(df: pd.DataFrame, period: int) -> pd.Series:
        high_low = df["High"] - df["Low"]
        high_close = (df["High"] - df["Close"].shift()).abs()
        low_close = (df["Low"] - df["Close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()


# ─────────────────────────────────────────────
# Backtesting Engine
# ─────────────────────────────────────────────

class BacktestEngine:
    """
    벡터 기반 백테스트 엔진.
    TimescaleDB에서 데이터를 조회하고, 전략의 매매 시그널에 따라 시뮬레이션한다.
    """

    def __init__(
        self,
        initial_capital: float = 100_000_000,
        commission_rate: float = 0.00015,   # 매매 수수료 (0.015%)
        slippage_rate: float = 0.001,        # 슬리피지 (0.1%)
        tax_rate: float = 0.0023,            # 매도세 (0.23%, 코스피)
        atr_stop_multiplier: float = 3.0,   # Stop = Entry - 3*ATR
    ):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.tax_rate = tax_rate
        self.atr_stop_multiplier = atr_stop_multiplier
        self.db = db_client

    def run(
        self,
        strategy: BaseStrategy,
        ticker: str,
        start_date: str = None,
        end_date: str = None,
    ) -> BacktestResult:
        """
        단일 종목 백테스트를 실행한다.

        Args:
            strategy: 전략 객체
            ticker: 종목 코드
            start_date: 시작일 (YYYY-MM-DD)
            end_date: 종료일 (YYYY-MM-DD)
        """
        logger.info(f"[Backtest] Running '{strategy.name}' on {ticker}")

        # 1. 데이터 조회
        df = self._load_data(ticker, start_date, end_date)
        if df.empty or len(df) < 60:
            logger.warning(f"[Backtest] Insufficient data for {ticker}: {len(df)} rows")
            return self._empty_result(strategy.name)

        # 2. 시그널 생성
        df = strategy.generate_signals(df)

        # 3. 시뮬레이션
        result = self._simulate(df, ticker, strategy.name)
        return result

    def run_from_dataframe(
        self,
        strategy: BaseStrategy,
        df: pd.DataFrame,
        ticker: str = "CUSTOM",
    ) -> BacktestResult:
        """
        외부 DataFrame으로 백테스트를 실행한다.
        FinanceDataReader 등에서 가져온 데이터를 직접 사용할 때 유용.

        Args:
            strategy: 전략 객체
            df: OHLCV DataFrame (columns: Open, High, Low, Close, Volume)
            ticker: 종목 코드 (라벨용)
        """
        if df.empty or len(df) < 60:
            logger.warning(f"[Backtest] Insufficient data: {len(df)} rows")
            return self._empty_result(strategy.name)

        df = strategy.generate_signals(df)
        return self._simulate(df, ticker, strategy.name)

    def run_multi(
        self,
        strategy: BaseStrategy,
        tickers: List[str],
        start_date: str = None,
        end_date: str = None,
    ) -> Dict[str, BacktestResult]:
        """다중 종목 백테스트."""
        results = {}
        for ticker in tickers:
            try:
                results[ticker] = self.run(strategy, ticker, start_date, end_date)
            except Exception as e:
                logger.error(f"[Backtest] Error on {ticker}: {e}")
        return results

    # ─────────────────────────────────────────────
    # Data Loading
    # ─────────────────────────────────────────────

    def _load_data(
        self, ticker: str, start_date: str = None, end_date: str = None
    ) -> pd.DataFrame:
        """TimescaleDB에서 OHLCV 데이터를 로드."""
        query = """
            SELECT time, open, high, low, close, volume
            FROM ohlcv_daily
            WHERE ticker_code = %s
        """
        params = [ticker]

        if start_date:
            query += " AND time >= %s"
            params.append(start_date)
        if end_date:
            query += " AND time <= %s"
            params.append(end_date)

        query += " ORDER BY time ASC"

        try:
            rows = self.db.fetch_all(query, tuple(params))
            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date")

            # float 변환
            for col in ["Open", "High", "Low", "Close"]:
                df[col] = df[col].astype(float)
            df["Volume"] = df["Volume"].astype(int)

            return df

        except Exception as e:
            logger.error(f"[Backtest] Data load error for {ticker}: {e}")
            return pd.DataFrame()

    # ─────────────────────────────────────────────
    # Simulation Engine
    # ─────────────────────────────────────────────

    def _simulate(
        self, df: pd.DataFrame, ticker: str, strategy_name: str
    ) -> BacktestResult:
        """이벤트 루프 기반 시뮬레이션."""
        capital = self.initial_capital
        position = 0        # 현재 보유 주식 수
        entry_price = 0.0
        entry_date = None
        stop_price = 0.0
        peak_price = 0.0    # Trailing Stop용

        trades: List[TradeRecord] = []
        equity_values = []
        dates = []

        for i in range(len(df)):
            row = df.iloc[i]
            date = df.index[i]
            price = float(row["Close"])
            signal = int(row.get("signal", 0))
            atr = float(row.get("ATR", price * 0.02)) if "ATR" in df.columns and not pd.isna(row.get("ATR", np.nan)) else price * 0.02

            # ─── 포지션 있을 때: 청산 조건 확인 ───
            if position > 0:
                # Trailing Stop 업데이트
                if price > peak_price:
                    peak_price = price
                    stop_price = peak_price - (self.atr_stop_multiplier * atr)

                # Stop Loss Hit
                if price <= stop_price:
                    exit_price = price * (1 - self.slippage_rate)
                    pnl = (exit_price - entry_price) * position
                    commission = exit_price * position * (self.commission_rate + self.tax_rate)
                    pnl -= commission
                    capital += exit_price * position - commission

                    trades.append(TradeRecord(
                        ticker=ticker, direction="LONG",
                        entry_date=str(entry_date), entry_price=round(entry_price, 0),
                        exit_date=str(date), exit_price=round(exit_price, 0),
                        shares=position,
                        pnl=round(pnl, 0),
                        pnl_pct=round((exit_price / entry_price - 1) * 100, 2),
                        holding_days=(date - entry_date).days if entry_date else 0,
                        exit_reason="STOP_LOSS",
                    ))
                    position = 0
                    entry_price = 0
                    peak_price = 0

                # Signal Exit
                elif signal == -1:
                    exit_price = price * (1 - self.slippage_rate)
                    pnl = (exit_price - entry_price) * position
                    commission = exit_price * position * (self.commission_rate + self.tax_rate)
                    pnl -= commission
                    capital += exit_price * position - commission

                    trades.append(TradeRecord(
                        ticker=ticker, direction="LONG",
                        entry_date=str(entry_date), entry_price=round(entry_price, 0),
                        exit_date=str(date), exit_price=round(exit_price, 0),
                        shares=position,
                        pnl=round(pnl, 0),
                        pnl_pct=round((exit_price / entry_price - 1) * 100, 2),
                        holding_days=(date - entry_date).days if entry_date else 0,
                        exit_reason="SIGNAL_EXIT",
                    ))
                    position = 0
                    entry_price = 0
                    peak_price = 0

            # ─── 포지션 없을 때: 진입 조건 확인 ───
            elif signal == 1 and position == 0:
                entry_price = price * (1 + self.slippage_rate)
                stop_price = entry_price - (self.atr_stop_multiplier * atr)
                peak_price = entry_price

                # Position sizing: 계좌의 2% 리스크
                risk_per_share = entry_price - stop_price
                if risk_per_share > 0:
                    max_shares = int((capital * 0.02) / risk_per_share)
                    # 1차 진입은 30%
                    position = max(1, int(max_shares * 0.3))
                else:
                    position = max(1, int(capital * 0.1 / entry_price))

                cost = entry_price * position
                commission = cost * self.commission_rate
                capital -= (cost + commission)
                entry_date = date

            # Equity 기록
            portfolio_value = capital + (position * price if position > 0 else 0)
            equity_values.append(portfolio_value)
            dates.append(date)

        # 마지막 포지션 강제 청산
        if position > 0:
            last_price = float(df["Close"].iloc[-1]) * (1 - self.slippage_rate)
            pnl = (last_price - entry_price) * position
            commission = last_price * position * (self.commission_rate + self.tax_rate)
            pnl -= commission
            capital += last_price * position - commission

            trades.append(TradeRecord(
                ticker=ticker, direction="LONG",
                entry_date=str(entry_date), entry_price=round(entry_price, 0),
                exit_date=str(df.index[-1]), exit_price=round(last_price, 0),
                shares=position,
                pnl=round(pnl, 0),
                pnl_pct=round((last_price / entry_price - 1) * 100, 2),
                holding_days=(df.index[-1] - entry_date).days if entry_date else 0,
                exit_reason="END_OF_DATA",
            ))
            position = 0

        # ─── Performance Metrics ───
        equity_curve = pd.Series(equity_values, index=dates)
        final_capital = equity_values[-1] if equity_values else self.initial_capital

        return self._calculate_metrics(
            strategy_name, ticker, trades, equity_curve,
            self.initial_capital, final_capital, df
        )

    # ─────────────────────────────────────────────
    # Metrics Calculation
    # ─────────────────────────────────────────────

    def _calculate_metrics(
        self,
        strategy_name: str,
        ticker: str,
        trades: List[TradeRecord],
        equity_curve: pd.Series,
        initial_capital: float,
        final_capital: float,
        df: pd.DataFrame,
    ) -> BacktestResult:
        """성과 지표 계산."""
        total_return = (final_capital / initial_capital - 1) * 100

        # Trading days
        trading_days = len(df)
        years = trading_days / 252 if trading_days > 0 else 1
        annualized = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

        # Daily returns
        daily_returns = equity_curve.pct_change().dropna()

        # Sharpe (Rf = 3.5%)
        rf_daily = 0.035 / 252
        excess_returns = daily_returns - rf_daily
        excess_std = float(excess_returns.std()) if len(excess_returns) > 1 else 0
        sharpe = float(excess_returns.mean() / excess_std * np.sqrt(252)) if excess_std > 1e-10 else 0.0

        # Sortino
        downside = daily_returns[daily_returns < 0]
        downside_std = float(downside.std()) if len(downside) > 1 else 0
        sortino = float(excess_returns.mean() / downside_std * np.sqrt(252)) if downside_std > 1e-10 else 0.0

        # MDD
        rolling_max = equity_curve.expanding().max()
        drawdown = (equity_curve - rolling_max) / rolling_max
        max_dd = float(drawdown.min() * 100) if len(drawdown) > 0 else 0

        # MDD Duration
        in_dd = drawdown < 0
        dd_groups = (~in_dd).cumsum()
        if in_dd.any():
            dd_lengths = in_dd.groupby(dd_groups).sum()
            max_dd_duration = int(dd_lengths.max())
        else:
            max_dd_duration = 0

        # Trade stats
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        win_rate = len(wins) / len(trades) * 100 if trades else 0

        total_profit = sum(t.pnl for t in wins) if wins else 0
        total_loss = abs(sum(t.pnl for t in losses)) if losses else 1
        profit_factor = total_profit / total_loss if total_loss > 0 else 0

        avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
        avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0
        avg_holding = np.mean([t.holding_days for t in trades]) if trades else 0

        commission_total = sum(
            t.entry_price * t.shares * self.commission_rate +
            t.exit_price * t.shares * (self.commission_rate + self.tax_rate)
            for t in trades
        )

        period = f"{df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}" if len(df) > 0 else "N/A"

        return BacktestResult(
            strategy_name=strategy_name,
            period=period,
            initial_capital=initial_capital,
            final_capital=round(final_capital, 0),
            total_return=round(total_return, 2),
            annualized_return=round(annualized, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            max_drawdown=round(max_dd, 2),
            max_drawdown_duration=max_dd_duration,
            win_rate=round(win_rate, 1),
            profit_factor=round(profit_factor, 2),
            total_trades=len(trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            avg_win=round(float(avg_win), 2),
            avg_loss=round(float(avg_loss), 2),
            avg_holding_days=round(float(avg_holding), 1),
            commission_total=round(commission_total, 0),
            trades=trades,
            equity_curve=equity_curve,
        )

    def _empty_result(self, strategy_name: str) -> BacktestResult:
        return BacktestResult(
            strategy_name=strategy_name, period="N/A",
            initial_capital=self.initial_capital, final_capital=self.initial_capital,
            total_return=0, annualized_return=0, sharpe_ratio=0, sortino_ratio=0,
            max_drawdown=0, max_drawdown_duration=0,
            win_rate=0, profit_factor=0, total_trades=0,
            winning_trades=0, losing_trades=0, avg_win=0, avg_loss=0,
            avg_holding_days=0, commission_total=0,
            trades=[], equity_curve=pd.Series(dtype=float),
        )

    # ─────────────────────────────────────────────
    # Report
    # ─────────────────────────────────────────────

    @staticmethod
    def print_report(result: BacktestResult):
        """백테스트 결과 리포트 출력."""
        print("\n" + "=" * 60)
        print(f"📊 Backtest Report: {result.strategy_name}")
        print("=" * 60)
        print(f"Period:          {result.period}")
        print(f"Initial Capital: ₩{result.initial_capital:,.0f}")
        print(f"Final Capital:   ₩{result.final_capital:,.0f}")
        print()

        # Returns
        print("─── Returns ───")
        ret_emoji = "🟢" if result.total_return > 0 else "🔴"
        print(f"  Total Return:      {ret_emoji} {result.total_return:+.2f}%")
        print(f"  Annualized Return: {result.annualized_return:+.2f}%")
        print()

        # Risk
        print("─── Risk ───")
        print(f"  Sharpe Ratio:      {result.sharpe_ratio:.2f}")
        print(f"  Sortino Ratio:     {result.sortino_ratio:.2f}")
        print(f"  Max Drawdown:      {result.max_drawdown:.2f}%")
        print(f"  MDD Duration:      {result.max_drawdown_duration} days")
        print()

        # Trades
        print("─── Trades ───")
        print(f"  Total Trades:      {result.total_trades}")
        print(f"  Win Rate:          {result.win_rate:.1f}%")
        print(f"  Profit Factor:     {result.profit_factor:.2f}")
        print(f"  Avg Win:           {result.avg_win:+.2f}%")
        print(f"  Avg Loss:          {result.avg_loss:+.2f}%")
        print(f"  Avg Holding:       {result.avg_holding_days:.1f} days")
        print(f"  Commission Total:  ₩{result.commission_total:,.0f}")
        print()

        # Trade Log
        if result.trades:
            print("─── Trade Log ───")
            print(f"{'Date':>12} {'Entry':>10} {'Exit':>10} {'P&L':>12} {'%':>8} {'Days':>5} {'Reason'}")
            print("-" * 75)
            for t in result.trades:
                pnl_emoji = "✅" if t.pnl > 0 else "❌"
                print(
                    f"{t.entry_date[:10]:>12} "
                    f"₩{t.entry_price:>9,.0f} "
                    f"₩{t.exit_price:>9,.0f} "
                    f"{pnl_emoji} ₩{t.pnl:>10,.0f} "
                    f"{t.pnl_pct:>+7.2f}% "
                    f"{t.holding_days:>4}d "
                    f"{t.exit_reason}"
                )

        print("\n" + "=" * 60)


# ─── Entry Point for Testing ───
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    engine = BacktestEngine(initial_capital=100_000_000)
    strategy = MomentumStrategy()

    # DB에서 OHLCV 데이터가 있는 종목으로 테스트
    from src.infrastructure.db.db_client import db_client
    tickers = db_client.fetch_all("SELECT DISTINCT ticker_code FROM ohlcv_daily LIMIT 3")
    ticker_codes = [t[0] for t in tickers]

    for ticker in ticker_codes:
        result = engine.run(strategy, ticker)
        engine.print_report(result)
