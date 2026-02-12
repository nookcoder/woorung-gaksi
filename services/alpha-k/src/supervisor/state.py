"""
Alpha-K Supervisor: LangGraph State Definition
================================================
5-Phase Pipeline의 상태를 정의한다.
"""
from __future__ import annotations
from typing import TypedDict, List, Dict, Any, Optional
import pandas as pd


class AlphaKState(TypedDict):
    """
    LangGraph 전체 State.
    Supervisor가 Phase를 관리하며 각 Agent가 결과를 기록한다.
    """
    # ─── Phase 1: Market Regime ───
    market_regime: Optional[Dict[str, Any]]
    # {regime, adr_20d, vkospi, bet_size_multiplier, reason, ...}

    # ─── Phase 2: Candidate Screening ───
    top_sectors: Optional[List[Dict[str, Any]]]
    candidate_tickers: Optional[List[str]]

    # ─── Phase 3: Deep Dive (per-ticker results) ───
    # Key: ticker, Value: result dict
    technical_results: Optional[Dict[str, Dict[str, Any]]]
    fundamental_results: Optional[Dict[str, Dict[str, Any]]]
    flow_results: Optional[Dict[str, Dict[str, Any]]]

    # ─── Phase 4: Scoring ───
    scored_candidates: Optional[List[Dict[str, Any]]]
    final_tickers: Optional[List[str]]  # Top 3

    # ─── Phase 5: Trade Setup ───
    trade_plans: Optional[List[Dict[str, Any]]]

    # ─── Report ───
    report: str

    # ─── Control ───
    current_phase: str  # "market_filter" | "screening" | "deep_dive" | "scoring" | "trade_setup" | "done"
    error: Optional[str]
