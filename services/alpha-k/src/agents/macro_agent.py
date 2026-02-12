"""
Alpha-K Agent: Macro Quant (Phase 1 - Market Filter)
=====================================================
rules/01_market_regime.md 구현체.
ADR, V-KOSPI, 환율 상관계수를 통해 시장 진입 여부를 판단한다.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict
import logging

from ..domain.models import MarketRegime, MarketRegimeResult
from ..infrastructure.data_providers.market_data import MarketDataProvider

logger = logging.getLogger(__name__)


class MacroAgent:
    """
    Phase 1: Market Regime 판단.
    - ADR 20일 이평 → 과매도/과매수
    - V-KOSPI 급등 + KOSPI < 20MA → HARD STOP
    - USD/KRW vs KOSPI 양의 상관 → 배팅 축소
    """

    def __init__(self, data: MarketDataProvider = None):
        self.data = data or MarketDataProvider()

    def analyze(self) -> MarketRegimeResult:
        """매크로 분석을 실행하고 MarketRegimeResult를 반환한다."""
        end = datetime.now()
        start = end - timedelta(days=90)
        start_str = start.strftime("%Y-%m-%d")
        end_str = end.strftime("%Y-%m-%d")

        # ─── 1. ADR 계산 ───
        adr_20d = self._calculate_adr(start_str, end_str)

        # ─── 2. V-KOSPI ───
        vkospi, vkospi_prev, kospi_above_20ma = self._check_vkospi(start_str, end_str)

        # ─── 3. 환율 상관계수 ───
        usd_krw_corr = self._calculate_fx_correlation(start_str, end_str)

        # ─── 판정 로직 ───
        regime, bet_size, reason = self._determine_regime(
            adr_20d, vkospi, vkospi_prev, kospi_above_20ma, usd_krw_corr
        )

        return MarketRegimeResult(
            regime=regime,
            adr_20d=adr_20d,
            vkospi=vkospi,
            vkospi_prev=vkospi_prev,
            kospi_above_20ma=kospi_above_20ma,
            usd_krw_corr=usd_krw_corr,
            bet_size_multiplier=bet_size,
            reason=reason,
        )

    def _calculate_adr(self, start: str, end: str) -> float:
        """
        ADR (Advance-Decline Ratio).
        FDR StockListing 스냅샷 기반 (오늘 기준).
        """
        try:
            adv, dec = self.data.get_advancing_declining(market="KOSPI")
            if dec > 0:
                return (adv / dec) * 100
            elif adv > 0:
                return 200.0
            return 100.0  # Neutral default

        except Exception as e:
            logger.error(f"[MacroAgent] ADR calculation failed: {e}")
            return 100.0  # Neutral fallback

    def _check_vkospi(self, start: str, end: str) -> tuple:
        """
        V-KOSPI 체크.
        Returns: (current_vkospi, previous_vkospi, kospi_above_20ma)
        """
        try:
            vkospi_df = self.data.get_vkospi(start, end)
            kospi_df = self.data.get_index("KS11", start, end)

            vkospi = float(vkospi_df['Close'].iloc[-1]) if not vkospi_df.empty and 'Close' in vkospi_df.columns else 20.0
            vkospi_prev = float(vkospi_df['Close'].iloc[-2]) if not vkospi_df.empty and len(vkospi_df) >= 2 and 'Close' in vkospi_df.columns else vkospi

            kospi_above_20ma = True
            if not kospi_df.empty and len(kospi_df) >= 20:
                ma20 = kospi_df['Close'].rolling(20).mean().iloc[-1]
                kospi_above_20ma = kospi_df['Close'].iloc[-1] > ma20

            return vkospi, vkospi_prev, kospi_above_20ma

        except Exception as e:
            logger.error(f"[MacroAgent] V-KOSPI check failed: {e}")
            return 20.0, 20.0, True

    def _calculate_fx_correlation(self, start: str, end: str) -> float:
        """
        USD/KRW vs KOSPI의 20일 Pearson 상관계수.
        양의 상관(> 0.2)이면 시장 디커플링 → 배팅 축소.
        """
        try:
            usd_krw = self.data.get_usd_krw(start, end)
            kospi = self.data.get_index("KS11", start, end)

            if usd_krw.empty or kospi.empty:
                return 0.0

            # 공통 날짜만 사용
            common_idx = usd_krw.index.intersection(kospi.index)
            if len(common_idx) < 20:
                return 0.0

            usd_series = usd_krw.loc[common_idx, 'Close'].pct_change().dropna()
            kospi_series = kospi.loc[common_idx, 'Close'].pct_change().dropna()

            # 다시 공통 index
            common = usd_series.index.intersection(kospi_series.index)
            if len(common) < 15:
                return 0.0

            corr = usd_series.loc[common].tail(20).corr(kospi_series.loc[common].tail(20))
            return float(corr) if not np.isnan(corr) else 0.0

        except Exception as e:
            logger.error(f"[MacroAgent] FX Correlation failed: {e}")
            return 0.0

    def _determine_regime(
        self, adr: float, vkospi: float, vkospi_prev: float,
        kospi_above_20ma: bool, fx_corr: float
    ) -> tuple:
        """규칙 기반 시장 국면 판정."""
        reasons = []
        bet_size = 1.0

        # ─── V-KOSPI HARD STOP ───
        if vkospi > vkospi_prev * 1.05 and not kospi_above_20ma:
            reasons.append(f"V-KOSPI 급등({vkospi:.1f} > {vkospi_prev:.1f}*1.05) + KOSPI < 20MA → HARD STOP")
            return MarketRegime.CRASH, 0.0, " | ".join(reasons)

        # ─── ADR 기반 ───
        if adr < 75:
            reasons.append(f"ADR={adr:.1f} < 75 (Panic/Oversold → Aggressive Buy)")
            regime = MarketRegime.BULL  # 역발상: 공포 구간에서 적극 매수
            bet_size = 1.0
        elif adr > 120:
            reasons.append(f"ADR={adr:.1f} > 120 (Overbought/Euphoria → Reduce)")
            regime = MarketRegime.BEAR
            bet_size = 0.0
        else:
            reasons.append(f"ADR={adr:.1f} (Normal)")
            regime = MarketRegime.NORMAL
            bet_size = 1.0

        # ─── 환율 상관 보정 ───
        if fx_corr > 0.2:
            reasons.append(f"USD/KRW Corr={fx_corr:.2f} > 0.2 → 배팅 50% 축소")
            bet_size *= 0.5

        return regime, bet_size, " | ".join(reasons)
