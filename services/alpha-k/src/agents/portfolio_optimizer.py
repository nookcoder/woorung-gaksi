"""
Portfolio Optimizer (Phase 2.4)
===============================
후보 종목들을 포트폴리오 관점에서 최적화한다.

핵심 기능:
1. 상관관계 행렬 계산 → 고상관 종목 필터링
2. Risk Parity 포지션 사이징 (변동성 역수 배분)
3. Kelly Criterion 적용 (win_rate 기반)
4. VaR / Sharpe / MDD 산출

로드맵 참조: alpha_k_v2_roadmap.md §3
리스크 규칙 참조: 06_risk_management.md
"""
import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Tuple

from ..domain.models import (
    TradePlan,
    PortfolioAllocation,
    PortfolioRiskMetrics,
    OptimizedPortfolio,
)
from ..infrastructure.db.db_client import db_client

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    포트폴리오 최적화 엔진.

    입력: List[TradePlan] (RiskAgent에서 생성된 개별 매매 계획)
    출력: OptimizedPortfolio (최적화된 포트폴리오)
    """

    # ─── Configuration ───
    RISK_FREE_RATE = 0.035          # 한국 무위험 수익률 (국채 3.5%)
    MAX_CORRELATION = 0.80          # 상관계수 임계치 (초과 시 하나 제거)
    MAX_POSITIONS = 5               # 최대 포지션 수
    MIN_WEIGHT = 0.05               # 최소 배분 비율 (5%)
    MAX_WEIGHT = 0.40               # 최대 배분 비율 (40%)
    CASH_RESERVE_PCT = 0.10         # 현금 보유 비율 (10%)
    LOOKBACK_DAYS = 60              # 상관관계/변동성 계산 기간 (60영업일)
    ANNUALIZE_FACTOR = np.sqrt(252) # 연환산 변환 계수

    def __init__(self, account_balance: float = 100_000_000):
        self.account_balance = account_balance
        self.db = db_client
        self._returns_cache: Dict[str, pd.Series] = {}

    def optimize(
        self,
        trade_plans: List[TradePlan],
        method: str = "risk_parity",
    ) -> OptimizedPortfolio:
        """
        TradePlan 리스트를 받아 최적화된 포트폴리오를 생성한다.

        Steps:
        1. actionable한 종목만 필터링
        2. 수익률 데이터 조회 (TimescaleDB)
        3. 상관관계 행렬 → 고상관 종목 제거
        4. 포지션 사이징 (Risk Parity or Equal Weight)
        5. 리스크 지표 산출 (VaR, Sharpe, MDD)
        """
        logger.info(f"[PortfolioOptimizer] Optimizing {len(trade_plans)} candidates. Method: {method}")

        # 1. actionable한 종목만 필터
        actionable = [tp for tp in trade_plans if tp.is_actionable]
        if not actionable:
            logger.warning("[PortfolioOptimizer] No actionable trade plans.")
            return self._empty_portfolio(method)

        tickers = [tp.ticker for tp in actionable]
        logger.info(f"[PortfolioOptimizer] Actionable: {len(actionable)} tickers: {tickers}")

        # 2. 수익률 데이터 조회
        returns_df = self._get_returns_matrix(tickers)
        if returns_df.empty or len(returns_df.columns) < 2:
            logger.warning("[PortfolioOptimizer] Insufficient return data. Using equal weight.")
            return self._equal_weight_fallback(actionable, method)

        # 3. 상관관계 필터링
        corr_matrix = returns_df.corr()
        filtered_tickers, removed = self._filter_correlated(
            actionable, corr_matrix
        )

        if not filtered_tickers:
            logger.warning("[PortfolioOptimizer] All tickers filtered out. Using top 1.")
            filtered_tickers = [actionable[0]]

        # MAX_POSITIONS 제한
        filtered_tickers = filtered_tickers[: self.MAX_POSITIONS]
        filtered_ticker_codes = [tp.ticker for tp in filtered_tickers]

        # 4. 포지션 사이징
        returns_filtered = returns_df[
            [t for t in filtered_ticker_codes if t in returns_df.columns]
        ]

        if method == "risk_parity":
            weights = self._risk_parity_weights(returns_filtered)
        else:
            weights = self._equal_weights(len(filtered_tickers))

        # Weight Clipping
        weights = self._clip_weights(weights)

        # 5. Allocation 계산
        investable = self.account_balance * (1 - self.CASH_RESERVE_PCT)
        allocations = []

        for i, tp in enumerate(filtered_tickers):
            if i >= len(weights):
                break
            w = weights[i]
            amount = investable * w
            shares = int(amount / tp.entry_zone) if tp.entry_zone > 0 else 0
            vol = float(returns_filtered[tp.ticker].std() * self.ANNUALIZE_FACTOR) if tp.ticker in returns_filtered else 0

            # 다른 포트폴리오 종목과의 최대 상관계수
            max_corr = 0.0
            for other_tp in filtered_tickers:
                if other_tp.ticker != tp.ticker:
                    try:
                        c = abs(corr_matrix.loc[tp.ticker, other_tp.ticker])
                        max_corr = max(max_corr, c)
                    except KeyError:
                        pass

            allocations.append(PortfolioAllocation(
                ticker=tp.ticker,
                name=tp.name,
                weight=round(w, 4),
                shares=shares,
                allocated_amount=round(amount, 0),
                volatility=round(vol, 4),
                risk_contribution=round(w * vol, 4),  # 단순 근사
                correlation_max=round(max_corr, 4),
                entry_price=tp.entry_zone,
            ))

        # 6. 리스크 지표 계산
        risk_metrics = self._calculate_risk_metrics(
            returns_filtered, weights, corr_matrix, filtered_ticker_codes, investable
        )

        total_invested = sum(a.allocated_amount for a in allocations)
        cash_reserve = self.account_balance - total_invested

        portfolio = OptimizedPortfolio(
            allocations=allocations,
            risk_metrics=risk_metrics,
            total_invested=round(total_invested, 0),
            cash_reserve=round(cash_reserve, 0),
            num_positions=len(allocations),
            method=method,
            filtered_tickers=[tp.ticker for tp in removed] if removed else [],
            reason=self._build_reason(allocations, risk_metrics, removed),
        )

        logger.info(
            f"[PortfolioOptimizer] Done. {portfolio.num_positions} positions, "
            f"Sharpe: {risk_metrics.sharpe_ratio:.2f}, "
            f"Vol: {risk_metrics.portfolio_volatility:.1%}"
        )

        return portfolio

    # ─────────────────────────────────────────────
    # Data Access
    # ─────────────────────────────────────────────

    def _get_returns_matrix(self, tickers: List[str]) -> pd.DataFrame:
        """TimescaleDB에서 각 종목의 일간 수익률을 조회하여 DataFrame으로 반환."""
        all_returns = {}
        for ticker in tickers:
            try:
                rows = self.db.fetch_all(
                    """
                    SELECT time, close
                    FROM ohlcv_daily
                    WHERE ticker_code = %s
                    ORDER BY time DESC
                    LIMIT %s
                    """,
                    (ticker, self.LOOKBACK_DAYS + 1),
                )
                if len(rows) < 10:
                    logger.warning(f"[PortfolioOptimizer] Insufficient data for {ticker}: {len(rows)} rows")
                    continue

                df = pd.DataFrame(rows, columns=["time", "close"])
                df = df.sort_values("time")
                df["return"] = df["close"].pct_change()
                df = df.dropna()
                all_returns[ticker] = df.set_index("time")["return"]

            except Exception as e:
                logger.error(f"[PortfolioOptimizer] DB error for {ticker}: {e}")

        if not all_returns:
            return pd.DataFrame()

        return pd.DataFrame(all_returns).dropna()

    # ─────────────────────────────────────────────
    # Correlation Filtering
    # ─────────────────────────────────────────────

    def _filter_correlated(
        self, trade_plans: List[TradePlan], corr_matrix: pd.DataFrame
    ) -> Tuple[List[TradePlan], List[TradePlan]]:
        """
        상관계수 > MAX_CORRELATION인 종목 쌍에서 점수가 낮은 종목을 제거.
        composite_score가 없으므로 R/R ratio를 사용.
        """
        removed = []
        remaining = list(trade_plans)

        # R/R 기준 내림차순 정렬 (높은 R/R이 우선)
        remaining.sort(key=lambda tp: tp.risk_reward_ratio, reverse=True)

        tickers_in = [tp.ticker for tp in remaining]
        remove_set = set()

        for i in range(len(tickers_in)):
            if tickers_in[i] in remove_set:
                continue
            for j in range(i + 1, len(tickers_in)):
                if tickers_in[j] in remove_set:
                    continue
                try:
                    corr = abs(corr_matrix.loc[tickers_in[i], tickers_in[j]])
                    if corr > self.MAX_CORRELATION:
                        # j를 제거 (i가 R/R 높음, 정렬되어 있으므로)
                        remove_set.add(tickers_in[j])
                        logger.info(
                            f"[PortfolioOptimizer] Filtered {tickers_in[j]} "
                            f"(corr={corr:.2f} with {tickers_in[i]})"
                        )
                except KeyError:
                    pass

        filtered = [tp for tp in remaining if tp.ticker not in remove_set]
        removed = [tp for tp in remaining if tp.ticker in remove_set]

        return filtered, removed

    # ─────────────────────────────────────────────
    # Position Sizing
    # ─────────────────────────────────────────────

    def _risk_parity_weights(self, returns_df: pd.DataFrame) -> List[float]:
        """
        Risk Parity: 각 자산이 포트폴리오에 동일한 위험을 기여하도록 배분.
        단순 구현: 변동성의 역수에 비례하여 배분.
        """
        vols = returns_df.std() * self.ANNUALIZE_FACTOR
        if (vols == 0).any():
            return self._equal_weights(len(returns_df.columns))

        inv_vol = 1.0 / vols
        weights = inv_vol / inv_vol.sum()
        return weights.tolist()

    def _equal_weights(self, n: int) -> List[float]:
        """Equal Weight 배분."""
        if n == 0:
            return []
        return [1.0 / n] * n

    def _clip_weights(self, weights: List[float]) -> List[float]:
        """MIN_WEIGHT ~ MAX_WEIGHT 범위로 제한 후 정규화."""
        clipped = [max(self.MIN_WEIGHT, min(self.MAX_WEIGHT, w)) for w in weights]
        total = sum(clipped)
        if total > 0:
            clipped = [w / total for w in clipped]
        return clipped

    # ─────────────────────────────────────────────
    # Risk Metrics
    # ─────────────────────────────────────────────

    def _calculate_risk_metrics(
        self,
        returns_df: pd.DataFrame,
        weights: List[float],
        corr_matrix: pd.DataFrame,
        tickers: List[str],
        investable: float,
    ) -> PortfolioRiskMetrics:
        """포트폴리오 리스크 지표를 계산한다."""
        w = np.array(weights[: len(tickers)])
        available_tickers = [t for t in tickers if t in returns_df.columns]

        if len(available_tickers) < 2:
            return self._empty_risk_metrics()

        ret = returns_df[available_tickers]
        cov_matrix = ret.cov() * 252  # Annualized

        # Portfolio Volatility
        port_var = float(w.T @ cov_matrix.values @ w)
        port_vol = float(np.sqrt(port_var))

        # Individual volatilities
        ind_vols = ret.std() * self.ANNUALIZE_FACTOR

        # Diversification Ratio = Weighted avg vol / Portfolio vol
        weighted_avg_vol = float(np.sum(w * ind_vols.values))
        div_ratio = weighted_avg_vol / port_vol if port_vol > 0 else 1.0

        # Portfolio Returns
        port_returns = (ret * w).sum(axis=1)

        # Sharpe Ratio (annualized)
        mean_return = float(port_returns.mean() * 252)
        sharpe = (mean_return - self.RISK_FREE_RATE) / port_vol if port_vol > 0 else 0

        # VaR (Parametric)
        daily_port_vol = port_vol / self.ANNUALIZE_FACTOR
        var_95 = investable * daily_port_vol * 1.645  # 95%
        var_99 = investable * daily_port_vol * 2.326  # 99%

        # Max Drawdown (Historical)
        cumulative = (1 + port_returns).cumprod()
        rolling_max = cumulative.expanding().max()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_dd = float(drawdown.min()) if len(drawdown) > 0 else 0

        # Correlation Matrix (subset)
        corr_dict = {}
        for t in available_tickers:
            corr_dict[t] = {}
            for t2 in available_tickers:
                try:
                    corr_dict[t][t2] = round(float(corr_matrix.loc[t, t2]), 3)
                except KeyError:
                    corr_dict[t][t2] = 0.0

        return PortfolioRiskMetrics(
            portfolio_volatility=round(port_vol, 4),
            sharpe_ratio=round(sharpe, 4),
            var_95=round(var_95, 0),
            var_99=round(var_99, 0),
            max_drawdown=round(max_dd, 4),
            diversification_ratio=round(div_ratio, 4),
            correlation_matrix=corr_dict,
        )

    # ─────────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────────

    def _build_reason(
        self,
        allocations: List[PortfolioAllocation],
        metrics: PortfolioRiskMetrics,
        removed: List[TradePlan],
    ) -> str:
        lines = []
        lines.append(f"포지션 {len(allocations)}개 구성")
        if removed:
            lines.append(f"상관관계 필터: {len(removed)}종목 제외 ({', '.join(r.ticker for r in removed)})")
        lines.append(f"Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
        lines.append(f"Portfolio Vol: {metrics.portfolio_volatility:.1%}")
        lines.append(f"분산비율: {metrics.diversification_ratio:.2f}")
        return " | ".join(lines)

    def _equal_weight_fallback(
        self, trade_plans: List[TradePlan], method: str
    ) -> OptimizedPortfolio:
        """데이터 부족 시 Equal Weight Fallback."""
        n = min(len(trade_plans), self.MAX_POSITIONS)
        plans = trade_plans[:n]
        investable = self.account_balance * (1 - self.CASH_RESERVE_PCT)
        w = 1.0 / n if n > 0 else 0

        allocations = []
        for tp in plans:
            amount = investable * w
            shares = int(amount / tp.entry_zone) if tp.entry_zone > 0 else 0
            allocations.append(PortfolioAllocation(
                ticker=tp.ticker, name=tp.name, weight=round(w, 4),
                shares=shares, allocated_amount=round(amount, 0),
                volatility=0, risk_contribution=0, correlation_max=0,
                entry_price=tp.entry_zone,
            ))

        return OptimizedPortfolio(
            allocations=allocations,
            risk_metrics=self._empty_risk_metrics(),
            total_invested=round(sum(a.allocated_amount for a in allocations), 0),
            cash_reserve=round(self.account_balance - sum(a.allocated_amount for a in allocations), 0),
            num_positions=len(allocations),
            method="equal_weight (fallback)",
            filtered_tickers=[],
            reason="데이터 부족으로 Equal Weight 적용",
        )

    def _empty_portfolio(self, method: str) -> OptimizedPortfolio:
        return OptimizedPortfolio(
            allocations=[], risk_metrics=self._empty_risk_metrics(),
            total_invested=0, cash_reserve=self.account_balance,
            num_positions=0, method=method, filtered_tickers=[],
            reason="actionable 종목 없음",
        )

    def _empty_risk_metrics(self) -> PortfolioRiskMetrics:
        return PortfolioRiskMetrics(
            portfolio_volatility=0, sharpe_ratio=0,
            var_95=0, var_99=0, max_drawdown=0,
            diversification_ratio=0, correlation_matrix={},
        )

    # ─────────────────────────────────────────────
    # Reporting
    # ─────────────────────────────────────────────

    def print_report(self, portfolio: OptimizedPortfolio):
        """포트폴리오 최적화 결과를 포맷팅하여 출력."""
        print("\n" + "=" * 60)
        print("📊 Portfolio Optimization Report")
        print("=" * 60)
        print(f"Method: {portfolio.method}")
        print(f"Positions: {portfolio.num_positions}")
        print(f"Total Invested: ₩{portfolio.total_invested:,.0f}")
        print(f"Cash Reserve: ₩{portfolio.cash_reserve:,.0f}")
        if portfolio.filtered_tickers:
            print(f"Filtered (High Corr): {portfolio.filtered_tickers}")
        print()

        # Allocations
        print("─" * 60)
        print(f"{'Ticker':<10} {'Weight':>8} {'Amount':>15} {'Shares':>8} {'Vol':>8} {'MaxCorr':>8}")
        print("─" * 60)
        for a in portfolio.allocations:
            print(
                f"{a.ticker:<10} {a.weight:>7.1%} "
                f"₩{a.allocated_amount:>13,.0f} {a.shares:>8,} "
                f"{a.volatility:>7.1%} {a.correlation_max:>7.2f}"
            )
        print()

        # Risk Metrics
        m = portfolio.risk_metrics
        print("─── Risk Metrics ───")
        print(f"  Portfolio Vol (Ann.): {m.portfolio_volatility:.1%}")
        print(f"  Sharpe Ratio:         {m.sharpe_ratio:.2f}")
        print(f"  VaR 95% (1D):        ₩{m.var_95:,.0f}")
        print(f"  VaR 99% (1D):        ₩{m.var_99:,.0f}")
        print(f"  Max Drawdown:         {m.max_drawdown:.1%}")
        print(f"  Diversification:      {m.diversification_ratio:.2f}")

        # Correlation Matrix
        if m.correlation_matrix:
            print("\n─── Correlation Matrix ───")
            tickers = list(m.correlation_matrix.keys())
            header = f"{'':>10}" + "".join(f"{t:>10}" for t in tickers)
            print(header)
            for t in tickers:
                row = f"{t:>10}"
                for t2 in tickers:
                    row += f"{m.correlation_matrix[t].get(t2, 0):>10.3f}"
                print(row)

        print("\n" + "=" * 60)
        print(f"📝 {portfolio.reason}")
        print("=" * 60)


# ─── Entry Point for Testing ───
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Simulate trade plans (normally from RiskAgent)
    from ..domain.models import TradePlan

    test_plans = [
        TradePlan(ticker="005930", name="삼성전자", buy_reason="Test",
                  entry_zone=85000, stop_loss=80000, target_price=95000,
                  risk_reward_ratio=2.0, atr_14=1500, pyramiding=[],
                  position_size_shares=100, is_actionable=True),
        TradePlan(ticker="000660", name="SK하이닉스", buy_reason="Test",
                  entry_zone=180000, stop_loss=170000, target_price=210000,
                  risk_reward_ratio=3.0, atr_14=5000, pyramiding=[],
                  position_size_shares=50, is_actionable=True),
        TradePlan(ticker="035420", name="NAVER", buy_reason="Test",
                  entry_zone=220000, stop_loss=210000, target_price=250000,
                  risk_reward_ratio=3.0, atr_14=6000, pyramiding=[],
                  position_size_shares=30, is_actionable=True),
    ]

    optimizer = PortfolioOptimizer(account_balance=100_000_000)
    result = optimizer.optimize(test_plans, method="risk_parity")
    optimizer.print_report(result)
