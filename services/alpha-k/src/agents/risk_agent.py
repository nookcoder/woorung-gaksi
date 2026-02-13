"""
Alpha-K Agent: Risk Executioner (Phase 5) v2
=============================================
rules/06_risk_management.md 구현체.
ATR 기반 동적 손절, 피라미딩 계획, R/R 비율 검증.

[v2] Neo4j 공급망 리스크 분석 추가:
  - 주요 공급업체/고객사의 이상 하락(>-5%) → 경고
  - 경쟁사 동향 참조
"""
import pandas as pd
import pandas_ta as ta  # type: ignore
from datetime import datetime, timedelta
from typing import List, Dict
import logging

from ..domain.models import TradePlan, TechnicalResult, SmartMoneyResult, FundamentalResult
from ..infrastructure.data_providers.market_data import MarketDataProvider
from ..infrastructure.graph.graph_service import graph_service

logger = logging.getLogger(__name__)


class RiskAgent:
    """
    Phase 5: 리스크 관리 및 매매 계획 수립.
    1) ATR(14) 기반 Dynamic Stop Loss
    2) Pyramiding: 30/30/40 분할 진입
    3) R/R Ratio >= 2.0 사전 검증
    4) [NEW] 공급망 리스크: Neo4j 그래프 기반
    """

    def __init__(
        self,
        account_balance: float = 100_000_000,  # 1억 원 기본
        max_risk_per_trade: float = 0.02,       # 매매당 최대 리스크 2%
        atr_multiplier: float = 3.0,            # Stop = Entry - 3 * ATR
        data: MarketDataProvider = None,
    ):
        self.account_balance = account_balance
        self.max_risk_per_trade = max_risk_per_trade
        self.atr_multiplier = atr_multiplier
        self.data = data or MarketDataProvider()
        self.graph = graph_service

    def create_trade_plan(
        self,
        ticker: str,
        df: pd.DataFrame,
        tech_result: TechnicalResult,
        fund_result: FundamentalResult,
        flow_result: SmartMoneyResult,
    ) -> TradePlan:
        """매매 계획을 수립한다."""
        if df.empty or len(df) < 14:
            return self._empty_plan(ticker)

        df = df.copy()
        df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        atr = float(df['ATR_14'].iloc[-1]) if not pd.isna(df['ATR_14'].iloc[-1]) else 0

        # ─── Entry Zone ───
        entry = tech_result.current_price
        if tech_result.vcp.detected and tech_result.vcp.pivot_point > 0:
            entry = tech_result.vcp.pivot_point
        elif tech_result.order_blocks:
            latest_ob = tech_result.order_blocks[-1]
            entry = latest_ob.top

        # ─── Stop Loss (06_risk_management.md) ───
        stop_loss = entry - (self.atr_multiplier * atr)
        if stop_loss <= 0:
            stop_loss = entry * 0.93  # 7% 최대 손절

        risk_per_share = entry - stop_loss

        # ─── Target Price ───
        target_by_rr = entry + (risk_per_share * 2.0)
        target_by_resistance = tech_result.resistance
        target = max(target_by_rr, target_by_resistance)

        # ─── R/R Ratio ───
        rr_ratio = (target - entry) / risk_per_share if risk_per_share > 0 else 0

        is_actionable = rr_ratio >= 2.0

        # ─── [NEW] Supply Chain Risk Check ───
        supply_chain_risk = self._check_supply_chain_risk(ticker)
        if supply_chain_risk:
            logger.warning(
                f"[RiskAgent] Supply chain risk for {ticker}: {supply_chain_risk}"
            )
            # 공급망 리스크 시 배팅 사이즈 30% 축소
            risk_adjustment = 0.7
        else:
            risk_adjustment = 1.0

        # ─── Position Sizing (Pyramiding) ───
        risk_amount = self.account_balance * self.max_risk_per_trade * risk_adjustment
        total_shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0

        pyramiding = [
            {"pct": 30, "shares": int(total_shares * 0.3), "trigger": "Initial Entry"},
            {"pct": 30, "shares": int(total_shares * 0.3), "trigger": "Profit > +3%"},
            {"pct": 40, "shares": total_shares - int(total_shares * 0.3) * 2, "trigger": "Profit > +5%"},
        ]

        # ─── Buy Reason ───
        buy_reason = self._build_buy_reason(
            tech_result, fund_result, flow_result, supply_chain_risk
        )

        name = ticker

        return TradePlan(
            ticker=ticker,
            name=name,
            buy_reason=buy_reason,
            entry_zone=round(entry, 0),
            stop_loss=round(stop_loss, 0),
            target_price=round(target, 0),
            risk_reward_ratio=round(rr_ratio, 2),
            atr_14=round(atr, 2),
            pyramiding=pyramiding,
            position_size_shares=int(total_shares * 0.3),  # 1차 진입 물량
            is_actionable=is_actionable,
        )

    # ──────────────────────────────────────────────────────────────────
    # [NEW] 공급망 리스크 분석
    # ──────────────────────────────────────────────────────────────────

    def _check_supply_chain_risk(self, ticker: str) -> List[str]:
        """
        Neo4j 공급망 데이터 + TimescaleDB 주가 데이터로 리스크 체크.
        - 주요 공급업체/고객사의 최근 5일 수익률 < -5% → 경고
        - 공급망 내 2-hop 종목 중 급락 종목이 있으면 경고
        """
        if not self.graph.is_available:
            return []

        risks = []
        try:
            supply_chain = self.graph.get_full_supply_chain(ticker)
            related = supply_chain.get("suppliers", []) + supply_chain.get("customers", [])

            if not related:
                return []

            end = datetime.now()
            start_5d = (end - timedelta(days=10)).strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")

            for rel in related[:8]:  # 최대 8개
                rel_code = rel["ticker_code"]
                rel_name = rel.get("ticker_name", rel_code)
                product = rel.get("product", "")

                try:
                    df = self.data.get_ohlcv(rel_code, start_5d, end_str)
                    if df.empty or len(df) < 2:
                        continue

                    # 최근 5일 수익률
                    ret_5d = (df['Close'].iloc[-1] / df['Close'].iloc[0]) - 1
                    if ret_5d < -0.05:
                        risks.append(
                            f"⚠️ {rel_name}({rel_code}) 5일 {ret_5d:.1%} 하락 "
                            f"[{product}] — 공급망 리스크"
                        )
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"[RiskAgent] Supply chain risk check failed: {e}")

        return risks

    # ──────────────────────────────────────────────────────────────────
    # Buy Reason
    # ──────────────────────────────────────────────────────────────────

    def _build_buy_reason(
        self, tech: TechnicalResult, fund: FundamentalResult,
        flow: SmartMoneyResult, supply_chain_risk: List[str] = None,
    ) -> str:
        """매수 근거 요약을 생성한다."""
        reasons = []

        # Technical
        if tech.vcp.detected:
            reasons.append(f"VCP 패턴(수축 {tech.vcp.tightness:.1f}%)")
        if tech.order_blocks:
            reasons.append(f"OB 지지(₩{tech.order_blocks[-1].bottom:,.0f})")
        if tech.price_above_poc:
            reasons.append("POC 위")

        # Fundamental
        reasons.append(f"F-Score {fund.f_score}/9")

        # Flow
        if flow.accumulation_days >= 3:
            reasons.append(f"매집 {flow.accumulation_days}일 연속")
        if flow.net_foreign_amount > 0:
            reasons.append(f"외인 순매수 {flow.net_foreign_amount:,.0f}M")

        # [NEW] Supply Chain Risk
        if supply_chain_risk:
            reasons.append(f"⚠️ 공급망 리스크 {len(supply_chain_risk)}건")

        return " | ".join(reasons) if reasons else "N/A"

    def _empty_plan(self, ticker: str) -> TradePlan:
        return TradePlan(
            ticker=ticker, name=ticker, buy_reason="Insufficient data",
            entry_zone=0, stop_loss=0, target_price=0,
            risk_reward_ratio=0, atr_14=0, pyramiding=[],
            position_size_shares=0, is_actionable=False,
        )
