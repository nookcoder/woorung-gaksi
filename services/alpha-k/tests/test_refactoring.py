"""
Refactoring Verification Script
===============================
Tests the integration of TimescaleDB and Neo4j across the refactored agents.
"""
import sys
import os
import logging

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.infrastructure.data_providers.market_data import MarketDataProvider
from src.infrastructure.graph.graph_service import graph_service
from src.agents.sector_agent import SectorAgent
from src.agents.smart_money_agent import SmartMoneyAgent
from src.agents.fundamental_agent import FundamentalAgent
from src.agents.risk_agent import RiskAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_refactoring")

def test_market_data_provider():
    logger.info("--- Testing MarketDataProvider ---")
    mdp = MarketDataProvider()
    ticker = "005930" # Samsung Electronics
    
    # 1. OHLCV (TimescaleDB -> FDR)
    logger.info(f"Fetching OHLCV for {ticker}...")
    df = mdp.get_ohlcv(ticker, "2024-01-01", "2024-01-10")
    if not df.empty:
        logger.info(f"OHLCV Success: {len(df)} rows")
    else:
        logger.warning("OHLCV Failed or No Data")

    # 2. Investor Trading
    logger.info(f"Fetching Investor Data for {ticker}...")
    inv = mdp.get_investor_trading(ticker, days=10)
    if not inv.empty:
        logger.info(f"Investor Data Success: {len(inv)} rows")
    else:
        logger.warning("Investor Data Failed or No Data")

def test_graph_service():
    logger.info("\n--- Testing GraphService (Neo4j) ---")
    if not graph_service.is_available:
        logger.warning("Neo4j is NOT connected. Skipping tests.")
        return

    # 1. Themes
    themes = graph_service.get_all_themes()
    logger.info(f"All Themes: {len(themes)}")
    if themes:
        logger.info(f"Sample Theme: {themes[0]}")
    
    # 2. Theme Tickers
    if themes:
        theme_name = themes[0]['theme_name']
        tickers = graph_service.get_theme_tickers(theme_name)
        logger.info(f"Tickers in '{theme_name}': {len(tickers)}")

    # 3. Supply Chain
    ticker = "005930"
    sc = graph_service.get_full_supply_chain(ticker)
    logger.info(f"Supply Chain for {ticker}: {len(sc['suppliers'])} suppliers, {len(sc['customers'])} customers")


def test_agents():
    logger.info("\n--- Testing Agents ---")
    mdp = MarketDataProvider()

    # 1. Sector Agent (Neo4j Theme Expansion)
    logger.info("Testing SectorAgent...")
    sector_agent = SectorAgent(mdp)
    try:
        res = sector_agent.analyze()
        logger.info(f"Candidates: {len(res.candidate_tickers)}")
    except Exception as e:
        logger.error(f"SectorAgent Failed: {e}")

    # 2. Smart Money Agent (Group Alignment)
    logger.info("Testing SmartMoneyAgent...")
    sm_agent = SmartMoneyAgent(mdp)
    res_sm = sm_agent.analyze("005930")
    logger.info(f"Smart Money Result: {res_sm.flow_score} (Accum: {res_sm.accumulation_days})")

    # 3. Fundamental Agent (Peer Comparison)
    logger.info("Testing FundamentalAgent...")
    fund_agent = FundamentalAgent(data=mdp)
    # Mock financials
    financials = {
        "per": 10.0, "peg_ratio": 1.0, "roa": 0.1, "operating_cash_flow": 100,
        "net_income": 80, "current_ratio": 1.5, "gross_margin": 0.3
    }
    res_fund = fund_agent.analyze("005930", financials, sector_avg_per=0)
    logger.info(f"Fundamental Result: F-Score={res_fund.f_score}, Relative PER={res_fund.relative_per}")

    # 4. Risk Agent (Supply Chain Risk)
    logger.info("Testing RiskAgent...")
    risk_agent = RiskAgent(data=mdp)
    # Mock Objects
    from src.domain.models import TechnicalResult, VCPPattern
    tech_res = TechnicalResult("005930", 80, [], VCPPattern(False, [], 0, 0), 0, True, 70000, 80000, 60000, 50, 68000, 65000, 60000, True)
    
    # Mock DF
    import pandas as pd
    df = pd.DataFrame({
        'High': [71000]*20, 'Low': [69000]*20, 'Close': [70000]*20, 'Volume': [1000]*20
    })
    
    plan = risk_agent.create_trade_plan("005930", df, tech_res, res_fund, res_sm)
    logger.info(f"Trade Plan: {plan.buy_reason}")


if __name__ == "__main__":
    test_market_data_provider()
    test_graph_service()
    test_agents()
