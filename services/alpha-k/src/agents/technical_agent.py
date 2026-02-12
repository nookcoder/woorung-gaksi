"""
Alpha-K Agent: Technical Sniper (Phase 3A)
===========================================
rules/03_technical_strategy.md 구현체.
Order Block (SMC), VCP 패턴, Volume Profile(POC) 분석.
"""
import pandas as pd
import numpy as np
import pandas_ta as ta  # type: ignore
from typing import List, Dict, Optional
import logging

from ..domain.models import (
    TechnicalResult, OrderBlock, VCPPattern,
)
from ..infrastructure.data_providers.market_data import MarketDataProvider

logger = logging.getLogger(__name__)


class TechnicalAgent:
    """
    Phase 3A: 기술적 분석.
    1) Order Block: 강한 임펄스 직전 마지막 음봉 → 기관 매집 구간
    2) VCP: 3단계 변동성 축소 패턴 → 마지막 수축 고점 돌파 시 진입
    3) Volume Profile POC: 최대 거래 매물대 → 현재가가 POC 위에 있어야 함
    """

    def __init__(self, data: MarketDataProvider = None):
        self.data = data or MarketDataProvider()

    def analyze(self, ticker: str, df: pd.DataFrame) -> TechnicalResult:
        """종목의 기술적 분석을 수행한다."""
        if df.empty or len(df) < 60:
            return self._empty_result(ticker)

        # ─── 기본 지표 계산 ───
        df = df.copy()
        df['RSI_14'] = ta.rsi(df['Close'], length=14)
        df['EMA_20'] = ta.ema(df['Close'], length=20)
        df['EMA_50'] = ta.ema(df['Close'], length=50)
        df['EMA_60'] = ta.ema(df['Close'], length=60)
        df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        df['VOL_MA20'] = df['Volume'].rolling(20).mean()

        current_price = float(df['Close'].iloc[-1])
        rsi = float(df['RSI_14'].iloc[-1]) if not pd.isna(df['RSI_14'].iloc[-1]) else 50.0
        ema_20 = float(df['EMA_20'].iloc[-1]) if not pd.isna(df['EMA_20'].iloc[-1]) else current_price
        ema_50 = float(df['EMA_50'].iloc[-1]) if not pd.isna(df['EMA_50'].iloc[-1]) else current_price
        ema_60 = float(df['EMA_60'].iloc[-1]) if not pd.isna(df['EMA_60'].iloc[-1]) else current_price

        vol_surge = bool(df['Volume'].iloc[-1] > df['VOL_MA20'].iloc[-1] * 2) if not pd.isna(df['VOL_MA20'].iloc[-1]) else False

        # ─── 1. Order Block 탐지 (SMC) ───
        order_blocks = self._detect_order_blocks(df)

        # ─── 2. VCP 패턴 ───
        vcp = self._detect_vcp(df)

        # ─── 3. Volume Profile POC ───
        poc = self._calculate_poc(df, window=60)
        price_above_poc = current_price > poc

        # ─── 지지/저항선 계산 ───
        resistance = self._find_resistance(df)
        support = self._find_support(df, order_blocks)

        # ─── 종합 점수 ───
        score = self._calculate_score(
            df, order_blocks, vcp, price_above_poc, vol_surge, current_price, ema_20, ema_50
        )

        return TechnicalResult(
            ticker=ticker,
            score=score,
            order_blocks=order_blocks,
            vcp=vcp,
            poc=poc,
            price_above_poc=price_above_poc,
            current_price=current_price,
            resistance=resistance,
            support=support,
            rsi_14=rsi,
            ema_20=ema_20,
            ema_50=ema_50,
            ema_60=ema_60,
            volume_surge=vol_surge,
        )

    # ──────────────────────────────────────────────────────────────────
    # 1. Order Block Detection (SMC)
    # ──────────────────────────────────────────────────────────────────

    def _detect_order_blocks(self, df: pd.DataFrame, lookback: int = 60) -> List[OrderBlock]:
        """
        Order Block 탐지.
        정의: 강한 상승 파동(Impulse Move) 직전 '마지막 음봉(Last Bearish Candle)'의 Body Range.
        
        Impulse Move 기준 (03_technical_strategy.md):
          - 일일 주가변화 > +4%
          - 거래량 > 20일 평균 거래량의 200%
          - 전 고점(Swing High) 돌파 (BOS)
        """
        obs: List[OrderBlock] = []
        recent = df.tail(lookback).copy()
        
        if len(recent) < 10:
            return obs

        # Swing High 계산 (5봉 기준 로컬 최고가)
        recent['swing_high'] = recent['High'].rolling(5, center=True).max()
        vol_ma20 = recent['Volume'].rolling(20).mean()

        for i in range(5, len(recent) - 1):
            row = recent.iloc[i]
            prev_day = recent.iloc[i - 1]

            # 임펄스 무브 조건 체크
            pct_change = (row['Close'] - prev_day['Close']) / prev_day['Close']
            vol_ratio = row['Volume'] / vol_ma20.iloc[i] if not pd.isna(vol_ma20.iloc[i]) and vol_ma20.iloc[i] > 0 else 0

            is_impulse = (pct_change > 0.04) and (vol_ratio > 2.0)

            if not is_impulse:
                continue

            # BOS (Break of Structure): 지난 20봉의 Swing High를 돌파했는지
            lookback_highs = recent['High'].iloc[max(0, i-20):i]
            prev_swing_high = lookback_highs.max() if not lookback_highs.empty else 0
            is_bos = row['Close'] > prev_swing_high

            if not is_bos:
                continue

            # 임펄스 직전 '마지막 음봉' 찾기 (최대 5봉 이내)
            for j in range(i - 1, max(i - 6, 0), -1):
                candle = recent.iloc[j]
                if candle['Close'] < candle['Open']:  # 음봉
                    obs.append(OrderBlock(
                        ob_type='bullish',
                        top=float(candle['Open']),     # 음봉 Body 상단 = 시가
                        bottom=float(candle['Close']),  # 음봉 Body 하단 = 종가
                        date=str(recent.index[j]),
                        impulse_pct=round(pct_change * 100, 2),
                        volume_ratio=round(vol_ratio, 2),
                    ))
                    break

        return obs

    # ──────────────────────────────────────────────────────────────────
    # 2. VCP Pattern Detection (Minervini)
    # ──────────────────────────────────────────────────────────────────

    def _detect_vcp(self, df: pd.DataFrame, window: int = 120) -> VCPPattern:
        """
        Volatility Contraction Pattern 탐지.
        
        패턴 로직 (03_technical_strategy.md):
        - Phase 1: High-Low 하락폭 ~15-20%
        - Phase 2: High-Low 하락폭 ~8-10%
        - Phase 3: High-Low 하락폭 ~3-5% (가장 좁은 수축)
        - 각 수축 단계마다 거래량 감소 (Dry Up)
        - Pivot Point: 마지막 수축 고점 돌파
        """
        recent = df.tail(window).copy()
        if len(recent) < 40:
            return VCPPattern(detected=False, contractions=[], pivot_point=0, tightness=0)

        # 피봇 고점/저점 탐지 (7봉 기준)
        pivot_window = 7
        highs, lows = [], []

        for i in range(pivot_window, len(recent) - pivot_window):
            h = recent['High'].iloc[i]
            if h == recent['High'].iloc[i - pivot_window:i + pivot_window + 1].max():
                highs.append((i, float(h)))

            l = recent['Low'].iloc[i]
            if l == recent['Low'].iloc[i - pivot_window:i + pivot_window + 1].min():
                lows.append((i, float(l)))

        if len(highs) < 2 or len(lows) < 2:
            return VCPPattern(detected=False, contractions=[], pivot_point=0, tightness=0)

        # 수축(Contraction) 단계 식별
        contractions = []
        vol_ma20 = recent['Volume'].rolling(20).mean()

        for k in range(len(highs) - 1):
            h_idx, h_val = highs[k]
            # 이 고점 이후~다음 고점 이전까지의 최저점 찾기
            next_h_idx = highs[k + 1][0] if k + 1 < len(highs) else len(recent) - 1
            segment = recent.iloc[h_idx:next_h_idx + 1]

            if segment.empty:
                continue

            low_val = float(segment['Low'].min())
            depth_pct = ((h_val - low_val) / h_val) * 100

            # 해당 구간 평균 거래량 / 20일 평균 대비
            seg_vol = segment['Volume'].mean()
            overall_vol = vol_ma20.iloc[h_idx] if not pd.isna(vol_ma20.iloc[h_idx]) else 1
            vol_ratio = seg_vol / overall_vol if overall_vol > 0 else 1.0

            contractions.append({
                "depth_pct": round(depth_pct, 2),
                "volume_ratio": round(float(vol_ratio), 2),
            })

        if len(contractions) < 2:
            return VCPPattern(detected=False, contractions=contractions, pivot_point=0, tightness=0)

        # VCP 판정: 수축 깊이가 단계적으로 감소하고, 거래량도 줄어드는지
        depth_decreasing = all(
            contractions[i]["depth_pct"] > contractions[i + 1]["depth_pct"]
            for i in range(len(contractions) - 1)
        )
        vol_decreasing = all(
            contractions[i]["volume_ratio"] >= contractions[i + 1]["volume_ratio"]
            for i in range(len(contractions) - 1)
        )

        is_vcp = depth_decreasing  # 최소한 깊이는 줄어들어야 함
        
        # Pivot Point = 마지막 고점
        pivot = float(highs[-1][1]) if highs else 0
        tightness = contractions[-1]["depth_pct"] if contractions else 0

        return VCPPattern(
            detected=is_vcp,
            contractions=contractions,
            pivot_point=pivot,
            tightness=tightness,
        )

    # ──────────────────────────────────────────────────────────────────
    # 3. Volume Profile POC
    # ──────────────────────────────────────────────────────────────────

    def _calculate_poc(self, df: pd.DataFrame, window: int = 60) -> float:
        """
        최근 N일 간의 Volume Profile에서 POC(Point of Control)를 계산한다.
        POC = 가장 많은 거래량이 발생한 가격대.
        """
        recent = df.tail(window)
        if recent.empty:
            return 0.0

        try:
            # 가격 범위를 50개 구간으로 나눠 각 구간별 거래량 합산
            price_min = float(recent['Low'].min())
            price_max = float(recent['High'].max())

            if price_max == price_min:
                return float(recent['Close'].iloc[-1])

            bins = np.linspace(price_min, price_max, 51)
            vol_profile = np.zeros(50)

            for _, row in recent.iterrows():
                # 해당 봉의 거래량을 High-Low 범위에 균등 분배
                low, high, vol = float(row['Low']), float(row['High']), float(row['Volume'])
                for b in range(50):
                    bin_low, bin_high = bins[b], bins[b + 1]
                    if bin_high >= low and bin_low <= high:
                        overlap = min(bin_high, high) - max(bin_low, low)
                        candle_range = high - low if high > low else 1
                        vol_profile[b] += vol * (overlap / candle_range)

            poc_bin = int(np.argmax(vol_profile))
            poc_price = (bins[poc_bin] + bins[poc_bin + 1]) / 2
            return round(poc_price, 2)

        except Exception as e:
            logger.error(f"[TechnicalAgent] POC calculation failed: {e}")
            return float(df['Close'].iloc[-1])

    # ──────────────────────────────────────────────────────────────────
    # Support / Resistance
    # ──────────────────────────────────────────────────────────────────

    def _find_resistance(self, df: pd.DataFrame) -> float:
        """간단한 저항선: 최근 60일 최고가"""
        return float(df['High'].tail(60).max())

    def _find_support(self, df: pd.DataFrame, obs: List[OrderBlock]) -> float:
        """지지선: 가장 최근 Bullish OB의 bottom, 없으면 60일 최저가"""
        if obs:
            return obs[-1].bottom
        return float(df['Low'].tail(60).min())

    # ──────────────────────────────────────────────────────────────────
    # Scoring
    # ──────────────────────────────────────────────────────────────────

    def _calculate_score(
        self, df, obs, vcp, price_above_poc, vol_surge,
        current_price, ema_20, ema_50
    ) -> float:
        """
        기술적 점수 (0-100).
        - 트렌드 (EMA 정배열): +15
        - VCP 패턴: +25
        - Order Block 지지: +20
        - POC 위: +15
        - 거래량 급등: +10
        - RSI 40-70 (건강한 상승): +15
        """
        score = 0.0

        # 트렌드 (EMA 정배열)
        if current_price > ema_20 > ema_50:
            score += 15
        elif current_price > ema_20:
            score += 8

        # VCP
        if vcp.detected:
            score += 25
            # 마지막 수축이 매우 타이트하면 보너스
            if vcp.tightness < 5:
                score += 5

        # Order Block
        if obs:
            latest_ob = obs[-1]
            # 현재가가 OB 근처(위)에 있으면 지지 확인
            if current_price >= latest_ob.bottom:
                score += 20
            else:
                score += 5  # OB 있지만 아래에 있음

        # POC
        if price_above_poc:
            score += 15

        # Volume
        if vol_surge:
            score += 10

        # RSI
        rsi = float(df['RSI_14'].iloc[-1]) if not pd.isna(df['RSI_14'].iloc[-1]) else 50
        if 40 <= rsi <= 70:
            score += 15
        elif rsi < 40:
            score += 5  # 과매도 구간 (반등 가능)

        return min(100.0, score)

    def _empty_result(self, ticker: str) -> TechnicalResult:
        return TechnicalResult(
            ticker=ticker, score=0, order_blocks=[],
            vcp=VCPPattern(False, [], 0, 0),
            poc=0, price_above_poc=False,
            current_price=0, resistance=0, support=0,
            rsi_14=0, ema_20=0, ema_50=0, ema_60=0,
            volume_surge=False,
        )
