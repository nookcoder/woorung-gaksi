"""
Alpha-K: Multi-Agent Swing Trading System
==========================================
Entry Point. 5-Phase Pipeline을 실행한다.
"""
import argparse
import sys
import os
import logging
from datetime import datetime

# Setup path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("alpha-k")


def main():
    parser = argparse.ArgumentParser(
        description="Alpha-K Multi-Agent Swing Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline (auto sector screening)
  python src/main.py

  # Analyze specific tickers (skip Phase 1 & 2)
  python src/main.py --tickers 005930 000660 035420

  # Set account balance for position sizing
  python src/main.py --balance 50000000
        """,
    )
    parser.add_argument(
        "--tickers", nargs="+", type=str, default=None,
        help="Specific tickers to analyze (skips Phase 1 & 2 market/sector screening)"
    )
    parser.add_argument(
        "--balance", type=float, default=100_000_000,
        help="Account balance in KRW (default: 100,000,000)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output markdown report file path"
    )
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════╗")
    print("║     Alpha-K Trading System v1.0              ║")
    print("║     Multi-Agent Swing Trading Pipeline       ║")
    print(f"║     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                    ║")
    print("╚══════════════════════════════════════════════╝\n")

    from src.supervisor.graph import graph, risk_agent

    # Update risk agent balance
    risk_agent.account_balance = args.balance

    # ─── Build Initial State ───
    initial_state = {
        "market_regime": None,
        "top_sectors": None,
        "candidate_tickers": args.tickers,  # None = auto screening
        "technical_results": None,
        "fundamental_results": None,
        "flow_results": None,
        "scored_candidates": None,
        "final_tickers": None,
        "trade_plans": None,
        "report": "",
        "current_phase": "init",
        "error": None,
    }

    # ─── If specific tickers provided, skip Phase 1 & 2 ───
    if args.tickers:
        print(f"⚡ Direct Analysis Mode: {args.tickers}")
        print("   Skipping Phase 1 (Market Filter) & Phase 2 (Sector Screening)\n")

        # 직접 Phase 3부터 시작하기 위해 graph 대신 개별 실행
        from src.supervisor.graph import (
            deep_dive_node, scoring_node, trade_setup_node, report_node, market_filter_node
        )

        # Phase 1은 여전히 실행 (시장 상태 정보용)
        state = dict(initial_state)
        result = market_filter_node(state)
        state.update(result)

        # Phase 3: Deep Dive
        result = deep_dive_node(state)
        state.update(result)

        # Phase 4: Scoring
        result = scoring_node(state)
        state.update(result)

        # Phase 5: Trade Setup
        result = trade_setup_node(state)
        state.update(result)

        # Report
        result = report_node(state)
        state.update(result)

        final_state = state
    else:
        # ─── Full Pipeline via LangGraph ───
        try:
            final_state = graph.invoke(initial_state)
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    # ─── Output ───
    report = final_state.get("report", "")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n📄 Report saved to: {args.output}")
    elif not report:
        print("\n⚠️ No report generated (market may be in CRASH/BEAR mode)")

    print("\n✅ Alpha-K Pipeline Complete")


if __name__ == "__main__":
    main()
