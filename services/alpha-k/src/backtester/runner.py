"""
Backtest Runner
===============
Time-Travel 시뮬레이션의 메인 실행 루프.
지정된 기간 동안 TimeMachineProvider를 통해 과거 시점을 설정하고,
Supervisor(에이전트 파이프라인)를 실행하여 매매 계획을 수립,
VirtualBroker를 통해 가상 매매를 수행한다.
"""
from datetime import datetime, timedelta
import pandas as pd
from typing import List

from .time_machine import TimeMachineProvider
from .virtual_broker import VirtualBroker
from ..supervisor.graph import graph # LangGraph Compiled Object
from ..supervisor.state import AlphaKState
from ..infrastructure.data_providers.market_data import MarketDataProvider

# Patching MarketDataProvider globally for agents to pick up TimeMachineProvider
# (In a real DI container this would be cleaner)
# Here we rely on agents taking `data_provider` as arg or using the singleton.

class BacktestRunner:
    def __init__(self, start_date: str, end_date: str, initial_capital: float = 100_000_000):
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        
        self.provider = TimeMachineProvider()
        self.broker = VirtualBroker(initial_capital)
        
        # Inject provider into agents (re-initialize if needed)
        # For this prototype, we assume agents use the provider we pass or global one can be mocked.
        # But 'graph.py' instantiates agents globally. We might need to reload or patch.
        # For simplicity, we just set the date on provider, hoping agents use it if they use a shared instance.
        # However, graph.py creates its own 'data_provider = MarketDataProvider()'.
        # We must monkey-patch graph.py's data_provider.
        
        import services.alpha_k.src.supervisor.graph as supervisor_graph
        supervisor_graph.data_provider = self.provider
        supervisor_graph.macro_agent.data = self.provider
        supervisor_graph.sector_agent.data = self.provider
        supervisor_graph.technical_agent.data = self.provider
        supervisor_graph.smart_money_agent.data = self.provider
        # Fundamental/Risk might need it too
        
    def run(self):
        current = self.start_date
        
        while current <= self.end_date:
            date_str = current.strftime("%Y-%m-%d")
            print(f"\n--- [Backtest] Date: {date_str} ---")
            
            # 1. Time Travel
            self.provider.set_current_date(date_str)
            
            # 2. Run Pipeline (Supervisor)
            state = AlphaKState(
                current_phase="market_filter",
                market_regime={},
                top_sectors=[],
                candidate_tickers=[],
                technical_results={},
                fundamental_results={},
                flow_results={},
                scored_candidates=[],
                final_tickers=[],
                trade_plans=[],
                report="",
                force_analysis=True # To ensure we get trade plans even in neutral markets if we want to test stock picking
            )
            
            # Invoke Graph
            # result = graph.invoke(state) # This takes time.
            # For speed, we might want to run specific agents directly, but full graph is better for integrity.
            try:
                # Mocking graph invoke for now as it's complex and slow
                # In real imp, we call graph.invoke(state)
                # Here simulating getting trade plans from "RiskAgent"
                # ...
                pass 
            except Exception as e:
                print(f"Pipeline Error: {e}")

            # 3. Execution using Broker
            # Get plans from result['trade_plans']
            # self.broker.submit_plan(plan, date_str)
            
            # 4. Market Update (Close of Day)
            # Fetch OHLCV for all held positions to update PnL
            # market_data = {} ...
            # self.broker.process_market_data(date_str, market_data)
            
            current += timedelta(days=1)

        return self.broker.get_summary()

if __name__ == "__main__":
    runner = BacktestRunner("2024-01-01", "2024-01-31")
    res = runner.run()
    print(res)
