"""
Alpha-K Agent: Smart Money Flow (Phase 3C)
============================================
rules/05_smart_money.md 구현체.
프로그램 비차익 순매수, 거래원 분석, 연속 매집 판단.

데이터 소스: KIS Open API (투자자별 매매동향)
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict
import logging

from ..domain.models import SmartMoneyResult, FlowScore
from ..infrastructure.data_providers.market_data import MarketDataProvider

logger = logging.getLogger(__name__)


class SmartMoneyAgent:
    """
    Phase 3C: 수급 분석.
    1) 프로그램 비차익 순매수 → 양의 기울기(Positive Slope)
    2) 거래원 상위 5개사 분석 → (외인/기관 매수 > 개인 매수 * 2)
    3) 연속 매집: 최근 5일 중 기관/외인 순매수 3일 이상
    """

    def __init__(self, data: MarketDataProvider = None):
        self.data = data or MarketDataProvider()

    def analyze(self, ticker: str) -> SmartMoneyResult:
        """수급 분석을 수행한다."""
        # KIS API에서 투자자별 매매동향 조회 (최근 ~30거래일)
        inv_df = self.data.get_investor_trading(ticker)

        if inv_df.empty:
            logger.warning(f"[SmartMoneyAgent] No investor data for {ticker}")
            return self._empty_result(ticker)

        # ─── 1. 프로그램 비차익 분석 (Proxy: 기관 누적 추세) ───
        program_positive = self._check_program_buying(inv_df)

        # ─── 2. 거래원 분석 (외인/기관 vs 개인) ───
        foreign_inst_dominant = self._check_foreign_inst_dominance(inv_df)

        # ─── 3. 연속 매집 ───
        accum_days = self._check_continuous_accumulation(inv_df)

        # 순매수 금액 (최근 5일 합계, 백만원 단위)
        recent = inv_df.tail(5)
        net_foreign = float(recent['foreigner_net_amt'].sum()) if 'foreigner_net_amt' in recent.columns else 0
        net_inst = float(recent['institution_net_amt'].sum()) if 'institution_net_amt' in recent.columns else 0

        # ─── Flow Score 판정 ───
        flow_score = self._determine_flow_score(
            program_positive, foreign_inst_dominant, accum_days
        )

        return SmartMoneyResult(
            ticker=ticker,
            flow_score=flow_score,
            program_buying_positive=program_positive,
            foreign_inst_dominant=foreign_inst_dominant,
            accumulation_days=accum_days,
            net_foreign_amount=round(net_foreign / 1_000_000, 2),  # 백만원 단위
            net_inst_amount=round(net_inst / 1_000_000, 2),
        )

    def _check_program_buying(self, inv_df: pd.DataFrame) -> bool:
        """
        프로그램 비차익 순매수 확인.
        기관 순매수 누적 그래프의 기울기(Slope) > 0이면 Positive.
        (실제로는 KIS 프로그램매매 API로 보강 가능)
        """
        try:
            col = 'institution_net_qty' if 'institution_net_qty' in inv_df.columns else 'institution_net_amt'
            if col not in inv_df.columns:
                return False

            cumulative = inv_df[col].cumsum()
            if len(cumulative) < 5:
                return False

            recent_cum = cumulative.tail(10).values
            x = np.arange(len(recent_cum))

            if len(x) < 2:
                return False

            slope = np.polyfit(x, recent_cum, 1)[0]
            return slope > 0

        except Exception as e:
            logger.error(f"[SmartMoneyAgent] Program buying check failed: {e}")
            return False

    def _check_foreign_inst_dominance(self, inv_df: pd.DataFrame) -> bool:
        """
        외국인/기관 매수 > 개인 매수 * 2 (최근 5일 기준).
        05_smart_money.md: (Foreign/Inst Buy Volume) > (Retail Buy Volume * 2)
        """
        try:
            recent = inv_df.tail(5)

            # KIS API 컬럼: foreigner_net_qty, institution_net_qty, individual_net_qty
            fgn_col = 'foreigner_net_qty' if 'foreigner_net_qty' in recent.columns else 'foreigner_net_amt'
            inst_col = 'institution_net_qty' if 'institution_net_qty' in recent.columns else 'institution_net_amt'
            ind_col = 'individual_net_qty' if 'individual_net_qty' in recent.columns else 'individual_net_amt'

            if fgn_col not in recent.columns:
                return False

            foreign_buy = recent[fgn_col][recent[fgn_col] > 0].sum() if fgn_col in recent.columns else 0
            inst_buy = recent[inst_col][recent[inst_col] > 0].sum() if inst_col in recent.columns else 0
            individual_buy = abs(recent[ind_col][recent[ind_col] > 0].sum()) if ind_col in recent.columns else 0

            if individual_buy == 0:
                return (foreign_buy + inst_buy) > 0

            return (foreign_buy + inst_buy) > (individual_buy * 2)

        except Exception as e:
            logger.error(f"[SmartMoneyAgent] Dominance check failed: {e}")
            return False

    def _check_continuous_accumulation(self, inv_df: pd.DataFrame) -> int:
        """
        연속 매집: 최근 5거래일 중 기관 또는 외국인 순매수가 발생한 일수.
        05_smart_money.md: 3일 이상이면 Positive.
        """
        try:
            recent = inv_df.tail(5)
            count = 0

            fgn_col = 'foreigner_net_qty' if 'foreigner_net_qty' in recent.columns else 'foreigner_net_amt'
            inst_col = 'institution_net_qty' if 'institution_net_qty' in recent.columns else 'institution_net_amt'

            for _, row in recent.iterrows():
                inst = row.get(inst_col, 0)
                foreign = row.get(fgn_col, 0)
                if inst > 0 or foreign > 0:
                    count += 1

            return count

        except Exception as e:
            logger.error(f"[SmartMoneyAgent] Accumulation check failed: {e}")
            return 0

    def _determine_flow_score(
        self, program_positive: bool, foreign_inst_dominant: bool, accum_days: int
    ) -> FlowScore:
        """
        수급 점수 판정.
        - HIGH: 3가지 조건 중 2개 이상 충족 + 매집일 >= 3
        - MEDIUM: 1개 충족 또는 매집일 >= 2
        - LOW: 모두 미충족
        """
        signals = sum([program_positive, foreign_inst_dominant, accum_days >= 3])

        if signals >= 2 and accum_days >= 3:
            return FlowScore.HIGH
        elif signals >= 1 or accum_days >= 2:
            return FlowScore.MEDIUM
        else:
            return FlowScore.LOW

    def _empty_result(self, ticker: str) -> SmartMoneyResult:
        return SmartMoneyResult(
            ticker=ticker,
            flow_score=FlowScore.LOW,
            program_buying_positive=False,
            foreign_inst_dominant=False,
            accumulation_days=0,
            net_foreign_amount=0,
            net_inst_amount=0,
        )
