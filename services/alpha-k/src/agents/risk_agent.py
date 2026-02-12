"""
Alpha-K Agent: Risk Executioner (Phase 5)
==========================================
rules/06_risk_management.md 구현체.
ATR 기반 동적 손절, 피라미딩 계획, R/R 비율 검증.
"""
import pandas as pd
import pandas_ta as ta  # type: ignore
from typing import List, Dict
import logging

from ..domain.models import TradePlan, TechnicalResult, SmartMoneyResult, FundamentalResult

logger = logging.getLogger(__name__)


class RiskAgent:
    """
    Phase 5: 리스크 관리 및 매매 계획 수립.
    1) ATR(14) 기반 Dynamic Stop Loss
    2) Pyramiding: 30/30/40 분할 진입
    3) R/R Ratio >= 2.0 사전 검증
    """

    def __init__(
        self,
        account_balance: float = 100_000_000,  # 1억 원 기본
        max_risk_per_trade: float = 0.02,       # 매매당 최대 리스크 2%
        atr_multiplier: float = 3.0,            # Stop = Entry - 3 * ATR
    ):
        self.account_balance = account_balance
        self.max_risk_per_trade = max_risk_per_trade
        self.atr_multiplier = atr_multiplier

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
        # VCP 패턴 감지 시 → Pivot Point를 Entry로
        # Order Block 감지 시 → OB top을 Entry로
        # 기본: 현재가
        entry = tech_result.current_price
        if tech_result.vcp.detected and tech_result.vcp.pivot_point > 0:
            entry = tech_result.vcp.pivot_point
        elif tech_result.order_blocks:
            latest_ob = tech_result.order_blocks[-1]
            entry = latest_ob.top  # OB 상단 리테스트

        # ─── Stop Loss (06_risk_management.md) ───
        # Stop Price = Entry - 3 * ATR(14)
        stop_loss = entry - (self.atr_multiplier * atr)

        # 안전장치: 손절가가 0 이하가 되지 않도록
        if stop_loss <= 0:
            stop_loss = entry * 0.93  # 7% 최대 손절

        risk_per_share = entry - stop_loss

        # ─── Target Price ───
        # 1차 목표: 다음 저항선 또는 R/R 2.0 기준
        target_by_rr = entry + (risk_per_share * 2.0)
        target_by_resistance = tech_result.resistance

        target = max(target_by_rr, target_by_resistance)

        # ─── R/R Ratio ───
        rr_ratio = (target - entry) / risk_per_share if risk_per_share > 0 else 0

        # R/R < 2.0이면 진입 불가 (06_risk_management.md: Non-negotiable)
        is_actionable = rr_ratio >= 2.0

        # ─── Position Sizing (Pyramiding) ───
        # 06_risk_management.md: 30% → 30% → 40%
        risk_amount = self.account_balance * self.max_risk_per_trade
        total_shares = int(risk_amount / risk_per_share) if risk_per_share > 0 else 0

        pyramiding = [
            {"pct": 30, "shares": int(total_shares * 0.3), "trigger": "Initial Entry"},
            {"pct": 30, "shares": int(total_shares * 0.3), "trigger": "Profit > +3%"},
            {"pct": 40, "shares": total_shares - int(total_shares * 0.3) * 2, "trigger": "Profit > +5%"},
        ]

        # ─── Buy Reason ───
        buy_reason = self._build_buy_reason(tech_result, fund_result, flow_result)

        # 종목명은 ticker에서 추출 (별도 API 필요 시 확장)
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

    def _build_buy_reason(
        self, tech: TechnicalResult, fund: FundamentalResult, flow: SmartMoneyResult
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

        return " | ".join(reasons) if reasons else "N/A"

    def _empty_plan(self, ticker: str) -> TradePlan:
        return TradePlan(
            ticker=ticker, name=ticker, buy_reason="Insufficient data",
            entry_zone=0, stop_loss=0, target_price=0,
            risk_reward_ratio=0, atr_14=0, pyramiding=[],
            position_size_shares=0, is_actionable=False,
        )
