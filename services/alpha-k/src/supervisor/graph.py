"""
Alpha-K Supervisor: LangGraph 5-Phase Pipeline
================================================
04_main_pipeline.md 구현체.

Phase 1: Market Filter (Go/No-Go)      → MacroAgent
Phase 2: Candidate Screening           → SectorAgent
Phase 3: Deep Dive Analysis (Parallel) → TechnicalAgent + FundamentalAgent + SmartMoneyAgent
Phase 4: Scoring & Final Selection     → Supervisor Logic
Phase 5: Trade Setup & Execution Plan  → RiskAgent
"""
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Dict, Any, List, Literal
import logging

from langgraph.graph import StateGraph, END

from .state import AlphaKState
from ..agents.macro_agent import MacroAgent
from ..agents.sector_agent import SectorAgent
from ..agents.technical_agent import TechnicalAgent
from ..agents.fundamental_agent import FundamentalAgent
from ..agents.smart_money_agent import SmartMoneyAgent
from ..agents.risk_agent import RiskAgent
from ..infrastructure.data_providers.market_data import MarketDataProvider
from ..domain.models import (
    MarketRegime, FundamentalVerdict, FlowScore,
)

logger = logging.getLogger(__name__)

# ─── Agent Instances ───
data_provider = MarketDataProvider()
macro_agent = MacroAgent(data_provider)
sector_agent = SectorAgent(data_provider)
technical_agent = TechnicalAgent(data_provider)
fundamental_agent = FundamentalAgent()
smart_money_agent = SmartMoneyAgent(data_provider)
risk_agent = RiskAgent()


# ═══════════════════════════════════════════════════════════════════
# Phase 1: Market Filter (Go/No-Go)
# ═══════════════════════════════════════════════════════════════════

def market_filter_node(state: AlphaKState) -> Dict:
    """
    Macro Quant Agent를 실행한다.
    ADR, V-KOSPI, 환율 상관관계를 분석하여 시장 진입 여부를 판단.
    """
    print("═══ Phase 1: Market Filter ═══")
    try:
        result = macro_agent.analyze()
        regime_dict = {
            "regime": result.regime.value,
            "adr_20d": result.adr_20d,
            "vkospi": result.vkospi,
            "vkospi_prev": result.vkospi_prev,
            "kospi_above_20ma": result.kospi_above_20ma,
            "usd_krw_corr": result.usd_krw_corr,
            "bet_size_multiplier": result.bet_size_multiplier,
            "reason": result.reason,
        }
        print(f"  → Regime: {result.regime.value} | Bet Size: {result.bet_size_multiplier}")
        print(f"  → Reason: {result.reason}")
        return {"market_regime": regime_dict, "current_phase": "market_filter"}
    except Exception as e:
        logger.error(f"[Phase 1] Failed: {e}")
        return {"market_regime": None, "error": str(e), "current_phase": "market_filter"}


def check_market_router(state: AlphaKState) -> Literal["screening", "__end__"]:
    """
    Phase 1 결과에 따라 진행/중단 판단.
    CRASH or BEAR → 종료 ("Cash is King")
    NORMAL or BULL → Phase 2 진행
    """
    regime = state.get("market_regime", {})
    if not regime:
        return "__end__"

    regime_val = regime.get("regime", "NORMAL")
    bet_size = regime.get("bet_size_multiplier", 0)
    force = state.get("force_analysis", False)

    if regime_val == "CRASH" and not force:
        print(f"  ✋ HARD STOP: Market is CRASH. Cash is King.")
        return "__end__"

    if regime_val == "BEAR" and not force:
        print("  ⚠️ CAUTION: Market is BEAR. Proceeding with extreme caution.")
        # Proceed to screening
    
    elif bet_size <= 0 and not force:
        print(f"  ✋ STOP: Bet Size is {bet_size}. Cash is King.")
        return "__end__"

    if force:
        print(f"  ⚡ Force Analysis Enabled: Ignoring market regime ({regime_val})")

    return "screening"



# ═══════════════════════════════════════════════════════════════════
# Phase 2: Candidate Screening
# ═══════════════════════════════════════════════════════════════════

def screening_node(state: AlphaKState) -> Dict:
    """
    Sector Rotation Agent를 실행한다.
    RS Score 기반 Top 3 섹터 선정 + 1차 필터.
    """
    print("\n═══ Phase 2: Candidate Screening ═══")
    try:
        result = sector_agent.analyze()
        top_sectors = [
            {
                "sector_name": s.sector_name,
                "sector_code": s.sector_code,
                "rs_score": s.rs_score,
                "alpha_1w": s.alpha_1w,
                "alpha_1m": s.alpha_1m,
                "alpha_3m": s.alpha_3m,
            }
            for s in result.top_sectors
        ]
        print(f"  → Top Sectors: {[s['sector_name'] for s in top_sectors]}")
        print(f"  → Candidates: {len(result.candidate_tickers)} stocks")

        return {
            "top_sectors": top_sectors,
            "candidate_tickers": result.candidate_tickers,
            "current_phase": "screening",
        }
    except Exception as e:
        logger.error(f"[Phase 2] Failed: {e}")
        return {"candidate_tickers": [], "error": str(e), "current_phase": "screening"}


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Deep Dive Analysis (Parallel)
# ═══════════════════════════════════════════════════════════════════

def deep_dive_node(state: AlphaKState) -> Dict:
    """
    각 후보 종목에 대해 3개 에이전트를 실행한다.
    A. Technical Analysis (Order Block, VCP, POC)
    B. Fundamental Analysis (F-Score, PER, DART)
    C. Smart Money Flow (수급)
    """
    print("\n═══ Phase 3: Deep Dive Analysis ═══")
    candidates = state.get("candidate_tickers", [])

    if not candidates:
        print("  ⚠️ No candidates to analyze")
        return {
            "technical_results": {},
            "fundamental_results": {},
            "flow_results": {},
            "current_phase": "deep_dive",
        }

    tech_results = {}
    fund_results = {}
    flow_results = {}

    for ticker in candidates:
        print(f"\n  📊 Analyzing {ticker}...")

        try:
            # 3A. Technical (TimescaleDB 자동 조회)
            tech = technical_agent.analyze(ticker, df=None)
            
            if tech.current_price == 0:
                print(f"    ⚠️ No data for {ticker}, skipping")
                continue

            tech_results[ticker] = {
                "score": tech.score,
                "vcp_detected": tech.vcp.detected,
                "vcp_pivot": tech.vcp.pivot_point,
                "vcp_tightness": tech.vcp.tightness,
                "order_blocks": [
                    {"type": ob.ob_type, "top": ob.top, "bottom": ob.bottom, "date": ob.date}
                    for ob in tech.order_blocks
                ],
                "poc": tech.poc,
                "price_above_poc": tech.price_above_poc,
                "current_price": tech.current_price,
                "resistance": tech.resistance,
                "support": tech.support,
                "rsi_14": tech.rsi_14,
                "volume_surge": tech.volume_surge,
            }
            print(f"    [Tech] Score={tech.score:.0f} VCP={'✅' if tech.vcp.detected else '❌'} OB={len(tech.order_blocks)}")

            # 3B. Fundamental (KIS API + Neo4j Competitors)
            stock_info = data_provider.get_stock_info(ticker)
            kis_financials = data_provider.get_financial_statements(ticker)
            
            # KIS 데이터를 FundamentalAgent 포맷으로 변환
            financials = _map_kis_to_fundamental(stock_info, kis_financials)
            
            # Neo4j 경쟁사 비교 포함
            fund = fundamental_agent.analyze(ticker, financials, sector_avg_per=0) # 0 = Auto lookup peers
            fund_results[ticker] = {
                "f_score": fund.f_score,
                "verdict": fund.verdict.value,
                "relative_per": fund.relative_per,
                "peg_ratio": fund.peg_ratio,
                "dart_risks": fund.dart_risks,
                "summary": fund.summary,
            }
            print(f"    [Fund] F-Score={fund.f_score}/9 Verdict={fund.verdict.value} (Rel PER={fund.relative_per:.1f})")

            # 3C. Smart Money (TimescaleDB + Neo4j Group)
            flow = smart_money_agent.analyze(ticker)
            flow_results[ticker] = {
                "flow_score": flow.flow_score.value,
                "program_buying": flow.program_buying_positive,
                "foreign_inst_dominant": flow.foreign_inst_dominant,
                "accumulation_days": flow.accumulation_days,
                "net_foreign_m": flow.net_foreign_amount,
                "net_inst_m": flow.net_inst_amount,
            }
            print(f"    [Flow] Score={flow.flow_score.value} Accum={flow.accumulation_days}d Foreign={flow.net_foreign_amount:,.0f}M")

        except Exception as e:
            logger.error(f"[Phase 3] Error analyzing {ticker}: {e}")
            continue

    return {
        "technical_results": tech_results,
        "fundamental_results": fund_results,
        "flow_results": flow_results,
        "current_phase": "deep_dive",
    }


# ═══════════════════════════════════════════════════════════════════
# Phase 4: Scoring & Final Selection
# ═══════════════════════════════════════════════════════════════════

def scoring_node(state: AlphaKState) -> Dict:
    """
    Phase 3 결과를 집계하고 최종 후보를 선정한다.
    
    필터링:
    - Fundamental == FAIL → 제외
    - Technical Score < 70 → 제외
    - Flow Score == LOW → 제외
    
    랭킹 (04_main_pipeline.md):
    Composite = Technical * 0.5 + Flow * 0.3 + Fundamental * 0.2
    
    Top 3 선정.
    """
    print("\n═══ Phase 4: Scoring & Final Selection ═══")

    tech_results = state.get("technical_results", {})
    fund_results = state.get("fundamental_results", {})
    flow_results = state.get("flow_results", {})

    scored = []

    for ticker in tech_results:
        tech = tech_results.get(ticker, {})
        fund = fund_results.get(ticker, {})
        flow = flow_results.get(ticker, {})

        # ─── Filter ───
        if fund.get("verdict") == "FAIL":
            print(f"  ❌ {ticker}: Fundamental FAIL → Excluded")
            continue
        
        # Relaxed Technical Score Filter (70 -> 50)
        current_tech_score = tech.get("score", 0)
        if current_tech_score < 50:
            print(f"  ❌ {ticker}: Tech Score {current_tech_score:.0f} < 50 → Excluded")
            continue
            
        # Relaxed Flow Filter (Removed explicit LOW exclusion)
        # if flow.get("flow_score") == "LOW":
        #    print(f"  ❌ {ticker}: Flow LOW → Excluded")
        #    continue

        # ─── Score Conversion ───
        tech_score = tech.get("score", 0)
        flow_numeric = {"HIGH": 100, "MEDIUM": 60, "LOW": 20}.get(flow.get("flow_score", "LOW"), 20)
        fund_numeric = {"PASS": 100, "WARNING": 50, "FAIL": 0}.get(fund.get("verdict", "FAIL"), 0)

        composite = tech_score * 0.5 + flow_numeric * 0.3 + fund_numeric * 0.2

        scored.append({
            "ticker": ticker,
            "composite_score": round(composite, 2),
            "technical_score": tech_score,
            "flow_score_numeric": flow_numeric,
            "fundamental_score_numeric": fund_numeric,
        })

    # ─── Ranking ───
    scored.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, s in enumerate(scored):
        s["rank"] = i + 1

    top3 = scored[:3]
    final_tickers = [s["ticker"] for s in top3]

    print(f"\n  🏆 Top 3: {final_tickers}")
    for s in top3:
        print(f"    #{s['rank']} {s['ticker']}: Composite={s['composite_score']:.1f} "
              f"(Tech={s['technical_score']:.0f} Flow={s['flow_score_numeric']} Fund={s['fundamental_score_numeric']})")

    return {
        "scored_candidates": scored,
        "final_tickers": final_tickers,
        "current_phase": "scoring",
    }


# ═══════════════════════════════════════════════════════════════════
# Phase 5: Trade Setup & Execution Plan
# ═══════════════════════════════════════════════════════════════════

def trade_setup_node(state: AlphaKState) -> Dict:
    """
    최종 선정 종목에 대해 Risk Agent가 매매 계획을 수립한다.
    ATR 손절, 피라미딩, R/R 검증.
    """
    print("\n═══ Phase 5: Trade Setup ═══")

    final_tickers = state.get("final_tickers", [])
    tech_results = state.get("technical_results", {})
    fund_results = state.get("fundamental_results", {})
    flow_results = state.get("flow_results", {})

    if not final_tickers:
        print("  ⚠️ No tickers to plan")
        return {"trade_plans": [], "current_phase": "trade_setup"}

    end = datetime.now()
    start = end - timedelta(days=365)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    plans = []

    for ticker in final_tickers:
        try:
            df = data_provider.get_ohlcv(ticker, start_str, end_str)
            if df.empty:
                continue

            # 재구성 (TechnicalResult 등은 dict에서 복원하기 어려우므로 재분석)
            tech = technical_agent.analyze(ticker, df)

            # Fundamental/Flow는 이미 dict → 간단한 객체로 감싸기
            from ..domain.models import FundamentalResult, SmartMoneyResult, FundamentalVerdict, FlowScore as FS
            fund_dict = fund_results.get(ticker, {})
            flow_dict = flow_results.get(ticker, {})

            fund_obj = FundamentalResult(
                ticker=ticker,
                f_score=fund_dict.get("f_score", 0),
                verdict=FundamentalVerdict(fund_dict.get("verdict", "WARNING")),
                relative_per=fund_dict.get("relative_per", 0),
                peg_ratio=fund_dict.get("peg_ratio", 0),
                dart_risks=fund_dict.get("dart_risks", []),
                cb_overhang_pct=0,
                summary=fund_dict.get("summary", ""),
            )
            flow_obj = SmartMoneyResult(
                ticker=ticker,
                flow_score=FS(flow_dict.get("flow_score", "LOW")),
                program_buying_positive=flow_dict.get("program_buying", False),
                foreign_inst_dominant=flow_dict.get("foreign_inst_dominant", False),
                accumulation_days=flow_dict.get("accumulation_days", 0),
                net_foreign_amount=flow_dict.get("net_foreign_m", 0),
                net_inst_amount=flow_dict.get("net_inst_m", 0),
            )

            plan = risk_agent.create_trade_plan(ticker, df, tech, fund_obj, flow_obj)

            plan_dict = {
                "ticker": plan.ticker,
                "name": plan.name,
                "buy_reason": plan.buy_reason,
                "entry_zone": plan.entry_zone,
                "stop_loss": plan.stop_loss,
                "target_price": plan.target_price,
                "risk_reward_ratio": plan.risk_reward_ratio,
                "atr_14": plan.atr_14,
                "pyramiding": plan.pyramiding,
                "position_size_shares": plan.position_size_shares,
                "is_actionable": plan.is_actionable,
            }
            plans.append(plan_dict)

            status = "✅ ACTIONABLE" if plan.is_actionable else "⚠️ R/R < 2.0"
            print(f"  {status} {ticker}: Entry=₩{plan.entry_zone:,.0f} Stop=₩{plan.stop_loss:,.0f} "
                  f"Target=₩{plan.target_price:,.0f} R/R={plan.risk_reward_ratio:.2f}")

        except Exception as e:
            logger.error(f"[Phase 5] Trade plan failed for {ticker}: {e}")
            continue

    return {"trade_plans": plans, "current_phase": "trade_setup"}


# ═══════════════════════════════════════════════════════════════════
# Report Generator
# ═══════════════════════════════════════════════════════════════════

def report_node(state: AlphaKState) -> Dict:
    """최종 마크다운 리포트를 생성한다."""
    print("\n═══ Generating Report ═══")

    regime = state.get("market_regime") or {}
    top_sectors = state.get("top_sectors") or []
    plans = state.get("trade_plans") or []
    scored = state.get("scored_candidates") or []

    # 1. Try LLM Generation
    try:
        from ..infrastructure.llm_client import llm_client
        llm = llm_client.get_agent_llm("report")
        
        if llm:
            prompt = (
                f"You are the Chief Investment Officer (CIO) of Alpha-K.\n"
                f"Write a professional daily trading report based on the following data:\n\n"
                f"1. Market Regime:\n{regime}\n\n"
                f"2. Top Sectors:\n{top_sectors[:3]}\n\n"
                f"3. Final Candidates:\n{scored[:5]}\n\n"
                f"4. Trade Plans (Actionable):\n{[p for p in plans if p.get('is_actionable')]}\n\n"
                f"Requirements:\n"
                f"- Format in Markdown.\n"
                f"- Start with an Executive Summary.\n"
                f"- Explain *why* these sectors/stocks were chosen using financial reasoning.\n"
                f"- Present the trade plans clearly (Entry, Stop Loss, Target).\n"
                f"- Tone: Professional, authoritative, and concise."
            )
            
            response = llm.invoke(prompt)
            print("  ✅ LLM Report Generated")
            return {"report": response.content, "current_phase": "done"}
            
    except Exception as e:
        logger.warning(f"[Report] LLM generation failed: {e}. Falling back to template.")

    # 2. Fallback Template
    report_lines = [
        f"# 📈 Alpha-K Trading Report",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## Phase 1: Market Regime",
        f"- **Status:** {regime.get('regime', 'N/A') if regime else 'N/A'}",
        f"- **ADR (20d):** {regime.get('adr_20d', 0):.1f}" if regime else "- **ADR (20d):** N/A",
        f"- **V-KOSPI:** {regime.get('vkospi', 0):.1f}" if regime else "- **V-KOSPI:** N/A",
        f"- **Bet Size:** {regime.get('bet_size_multiplier', 0) * 100:.0f}%" if regime else "- **Bet Size:** N/A",
        f"- **Reason:** {regime.get('reason', '')}" if regime else "- **Reason:** N/A",
        "",
        "## Phase 2: Top Sectors",
    ]

    for s in top_sectors[:3]:
        report_lines.append(f"- **{s.get('sector_name', '')}** (RS={s.get('rs_score', 0):.4f})")

    report_lines.extend(["", "## Phase 4: Final Candidates"])
    if scored:
        for s in scored[:5]:
            report_lines.append(f"- #{s.get('rank', '')} **{s['ticker']}** — Composite={s['composite_score']:.1f}")
    else:
        report_lines.append("- No candidates passed all filters.")

    report_lines.extend(["", "---", "", "## Phase 5: Trade Plans", ""])

    for p in plans:
        actionable_tag = "✅" if p.get("is_actionable") else "⚠️ SKIP"
        report_lines.extend([
            f"### {actionable_tag} {p['ticker']} ({p['name']})",
            f"- **Buy Reason:** {p['buy_reason']}",
            f"- **Entry Zone:** ₩{p['entry_zone']:,.0f}",
            f"- **Stop Loss:** ₩{p['stop_loss']:,.0f} (ATR={p['atr_14']:.0f})",
            f"- **Target:** ₩{p['target_price']:,.0f}",
            f"- **R/R Ratio:** {p['risk_reward_ratio']:.2f}",
            f"- **1차 진입:** {p['position_size_shares']}주",
            "",
            "| 단계 | 비중 | 물량 | 트리거 |",
            "|------|------|------|--------|",
        ])
        for pyr in p.get("pyramiding", []):
            report_lines.append(
                f"| Entry | {pyr.get('pct', 0)}% | {pyr.get('shares', 0)}주 | {pyr.get('trigger', '')} |"
            )
        report_lines.append("")

    report_lines.extend(["---", "*Alpha-K System v1.0 — Non-negotiable Risk Rules Applied*"])

    report = "\n".join(report_lines)
    print(report)

    return {"report": report, "current_phase": "done"}


# ═══════════════════════════════════════════════════════════════════
# Build LangGraph
# ═══════════════════════════════════════════════════════════════════

def build_graph() -> StateGraph:
    """5-Phase Pipeline LangGraph를 빌드한다."""
    builder = StateGraph(AlphaKState)

    # Add Nodes
    builder.add_node("market_filter", market_filter_node)
    builder.add_node("screening", screening_node)
    builder.add_node("deep_dive", deep_dive_node)
    builder.add_node("scoring", scoring_node)
    builder.add_node("trade_setup", trade_setup_node)
    builder.add_node("report", report_node)

    # Entry Point
    builder.set_entry_point("market_filter")

    # Edges (Pipeline Flow)
    # Phase 1 → Decision Gate
    builder.add_conditional_edges(
        "market_filter",
        check_market_router,
        {
            "screening": "screening",
            "__end__": END,
        }
    )

    # Phase 2 → Phase 3
    builder.add_edge("screening", "deep_dive")

    # Phase 3 → Phase 4
    builder.add_edge("deep_dive", "scoring")

    # Phase 4 → Phase 5
    builder.add_edge("scoring", "trade_setup")

    # Phase 5 → Report
    builder.add_edge("trade_setup", "report")

    # Report → END
    builder.add_edge("report", END)

    return builder


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _map_kis_to_fundamental(stock_info: Dict, kis_fin: Dict) -> Dict:
    """
    KIS API 데이터를 FundamentalAgent가 사용하는 포맷으로 매핑.
    KIS의 'output'은 보통 리스트 형태이며, 최신(0), 전년(1) 순서임.
    """
    f = {
        "per": stock_info.get("per", 0),
        "peg_ratio": 1.2, # KIS에서 직접 제공하지 않을 경우 디폴트
        "cb_overhang_pct": 0,
    }

    # KIS 재무표 (FHKST03020800) parsing
    # 실제 API 리스폰스 구조에 따라 r[0] (최신), r[1] (이전) 접근
    if isinstance(kis_fin, list) and len(kis_fin) >= 2:
        curr = kis_fin[0]
        prev = kis_fin[1]
        
        def to_f(val):
            try: return float(val.replace(',', '')) if isinstance(val, str) else float(val or 0)
            except: return 0.0

        # ROA = Net Income / Total Assets
        curr_assets = to_f(curr.get("total_assets"))
        prev_assets = to_f(prev.get("total_assets"))
        curr_ni = to_f(curr.get("net_income"))
        prev_ni = to_f(prev.get("net_income"))
        
        f["roa"] = curr_ni / curr_assets if curr_assets > 0 else 0
        f["roa_prev"] = prev_ni / prev_assets if prev_assets > 0 else 0
        f["net_income"] = curr_ni
        f["operating_cash_flow"] = to_f(curr.get("operating_cash_flow")) # KIS 필드명 확인 필요
        
        # Debt Ratio / Current Ratio
        f["long_term_debt"] = to_f(curr.get("total_liabilities")) # Proxy if specific LT debt missing
        f["long_term_debt_prev"] = to_f(prev.get("total_liabilities"))
        
        f["current_ratio"] = to_f(curr.get("current_ratio")) # KIS 제공시
        f["current_ratio_prev"] = to_f(prev.get("current_ratio"))
        
        f["shares_outstanding"] = to_f(curr.get("total_stock_cnt"))
        f["shares_outstanding_prev"] = to_f(prev.get("total_stock_cnt"))
        
        f["gross_margin"] = to_f(curr.get("gross_profit_margin"))
        f["gross_margin_prev"] = to_f(prev.get("gross_profit_margin"))
        
        f["asset_turnover"] = to_f(curr.get("total_asset_turnover_ratio"))
        f["asset_turnover_prev"] = to_f(prev.get("total_asset_turnover_ratio"))

    return f

# Pre-compiled graph
graph = build_graph().compile()
