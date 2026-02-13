"""
Alpha-K Domain Models (Value Objects & Enums)
=============================================
모든 에이전트가 공유하는 데이터 구조를 정의한다.
DDD의 Value Object 패턴을 따른다.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────

class MarketRegime(str, Enum):
    """시장 국면 (Phase 1)"""
    CRASH = "CRASH"
    BEAR = "BEAR"
    NORMAL = "NORMAL"
    BULL = "BULL"


class FundamentalVerdict(str, Enum):
    """재무 분석 판정 (Phase 3B)"""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class FlowScore(str, Enum):
    """수급 점수 (Phase 3C)"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ─────────────────────────────────────────────
# Phase 1: Market Regime
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class MarketRegimeResult:
    """매크로 에이전트 분석 결과"""
    regime: MarketRegime
    adr_20d: float                  # 20일 이동평균 ADR
    vkospi: float                   # 현재 V-KOSPI
    vkospi_prev: float              # 전일 V-KOSPI
    kospi_above_20ma: bool          # KOSPI가 20MA 위인지
    usd_krw_corr: float             # USD/KRW vs KOSPI 20일 상관계수
    bet_size_multiplier: float      # 최종 배팅 사이즈 배수 (0.0 ~ 1.0)
    reason: str                     # 판단 근거


# ─────────────────────────────────────────────
# Phase 2: Sector Rotation
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class SectorScore:
    """개별 섹터 RS 점수"""
    sector_name: str
    sector_code: str
    rs_score: float
    alpha_1w: float
    alpha_1m: float
    alpha_3m: float
    trickle_down_ready: bool        # 낙수효과 조건 충족 여부


@dataclass
class CandidateScreeningResult:
    """후보 종목 스크리닝 결과"""
    top_sectors: List[SectorScore]
    candidate_tickers: List[str]    # 1차 필터 통과 종목
    total_scanned: int


# ─────────────────────────────────────────────
# Phase 3A: Technical Analysis
# ─────────────────────────────────────────────

@dataclass(frozen=True)
class OrderBlock:
    """기관 매집 구간 (Order Block)"""
    ob_type: str                    # 'bullish' or 'bearish'
    top: float
    bottom: float
    date: str
    impulse_pct: float              # 직후 임펄스 무브 상승률 (%)
    volume_ratio: float             # 임펄스 날 거래량 / 20일 평균


@dataclass(frozen=True)
class VCPPattern:
    """Volatility Contraction Pattern"""
    detected: bool
    contractions: List[Dict[str, float]]  # [{depth_pct, volume_ratio}]
    pivot_point: float              # 돌파 기준가
    tightness: float                # 마지막 수축 깊이 (%)


@dataclass
class TechnicalResult:
    """기술적 분석 결과"""
    ticker: str
    score: float                    # 0-100
    order_blocks: List[OrderBlock]
    vcp: VCPPattern
    poc: float                      # Volume Profile Point of Control
    price_above_poc: bool
    current_price: float
    resistance: float               # 다음 저항선
    support: float                  # 지지선
    rsi_14: float
    ema_20: float
    ema_50: float
    ema_60: float                   # 60일선 (1차 필터용)
    volume_surge: bool              # 거래량 급등 여부


# ─────────────────────────────────────────────
# Phase 3B: Fundamental Analysis
# ─────────────────────────────────────────────

@dataclass
class FundamentalResult:
    """재무 분석 결과"""
    ticker: str
    f_score: int                    # Piotroski F-Score (0-9)
    verdict: FundamentalVerdict
    relative_per: float             # 섹터 대비 상대 PER
    peg_ratio: float
    dart_risks: List[str]           # DART 공시 리스크 키워드
    cb_overhang_pct: float          # CB 잔액 / 시총 비율
    summary: str


# ─────────────────────────────────────────────
# Phase 3C: Smart Money Flow
# ─────────────────────────────────────────────

@dataclass
class SmartMoneyResult:
    """수급 분석 결과"""
    ticker: str
    flow_score: FlowScore
    program_buying_positive: bool   # 프로그램 비차익 순매수 우상향
    foreign_inst_dominant: bool     # 외국인/기관 매수 > 개인 매수 * 2
    accumulation_days: int          # 최근 5일 중 기관/외인 순매수 일수
    net_foreign_amount: float       # 외국인 순매수 금액 (백만원)
    net_inst_amount: float          # 기관 순매수 금액 (백만원)


# ─────────────────────────────────────────────
# Phase 4: Scoring & Selection
# ─────────────────────────────────────────────

@dataclass
class ScoredCandidate:
    """최종 점수가 매겨진 후보"""
    ticker: str
    composite_score: float          # 가중 합산 점수
    technical_score: float
    flow_score_numeric: float       # HIGH=100, MED=60, LOW=20
    fundamental_score_numeric: float  # PASS=100, WARNING=50, FAIL=0
    rank: int


# ─────────────────────────────────────────────
# Phase 5: Trade Setup
# ─────────────────────────────────────────────

@dataclass
class TradePlan:
    """최종 매매 계획"""
    ticker: str
    name: str
    buy_reason: str
    entry_zone: float               # 진입 예상가
    stop_loss: float                # 손절가 (ATR 기반)
    target_price: float             # 목표가
    risk_reward_ratio: float
    atr_14: float
    pyramiding: List[Dict[str, float]]  # [{pct: 30, trigger: "initial"}, ...]
    position_size_shares: int       # 1차 진입 물량
    is_actionable: bool             # R/R >= 2.0 여부


# ─────────────────────────────────────────────
# Final Report
# ─────────────────────────────────────────────

@dataclass
class AlphaKReport:
    """Alpha-K 최종 리포트"""
    market_regime: MarketRegimeResult
    screening: CandidateScreeningResult
    trade_plans: List[TradePlan]
    markdown: str                   # 최종 마크다운 리포트


# ─────────────────────────────────────────────
# Phase 6: Portfolio Optimization
# ─────────────────────────────────────────────

@dataclass
class PortfolioAllocation:
    """개별 종목 배분 결과"""
    ticker: str
    name: str
    weight: float                   # 배분 비율 (0.0 ~ 1.0)
    shares: int                     # 배분 주식 수
    allocated_amount: float         # 배분 금액 (원)
    volatility: float               # 연환산 변동성
    risk_contribution: float        # 포트폴리오 리스크 기여도 (%)
    correlation_max: float          # 포트폴리오 내 다른 종목과의 최대 상관계수
    entry_price: float              # 진입 예상가


@dataclass
class PortfolioRiskMetrics:
    """포트폴리오 전체 리스크 지표"""
    portfolio_volatility: float     # 연환산 포트폴리오 변동성
    sharpe_ratio: float             # Sharpe Ratio (Rf=3.5% 기준)
    var_95: float                   # 95% VaR (1일, 원)
    var_99: float                   # 99% VaR (1일, 원)
    max_drawdown: float             # 히스토리컬 MDD
    diversification_ratio: float    # 분산 비율 (높을수록 잘 분산됨)
    correlation_matrix: Dict        # {ticker: {ticker: corr}} 요약


@dataclass
class OptimizedPortfolio:
    """최적화된 포트폴리오"""
    allocations: List[PortfolioAllocation]
    risk_metrics: PortfolioRiskMetrics
    total_invested: float           # 총 투자금액
    cash_reserve: float             # 현금 보유 (미투자)
    num_positions: int              # 포지션 수
    method: str                     # 최적화 방법 (risk_parity, equal_weight, etc.)
    filtered_tickers: List[str]     # 상관관계 필터로 제외된 종목
    reason: str                     # 최적화 판단 요약
