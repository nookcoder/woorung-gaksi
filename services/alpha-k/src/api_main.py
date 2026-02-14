import sys
import os
import asyncio
import logging
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

# Setup path
# src 폴더의 상위 폴더(alpha-k)를 path에 추가하여 src.* 임포트가 가능하게 함
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(current_dir))

from dotenv import load_dotenv
load_dotenv()

from src.supervisor.graph import graph, risk_agent
from src.supervisor.graph import (
    market_filter_node, deep_dive_node, scoring_node, trade_setup_node, report_node
)
from src.infrastructure.db.migrator import run_migrations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("alpha-k-api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """컨테이너 시작 시 스케줄러를 백그라운드로 실행."""
    # Run DB Migrations
    try:
        run_migrations()
    except Exception as e:
        logger.error(f"Migration failed: {e}")

    from src.scheduler import run_scheduler
    scheduler_task = asyncio.create_task(run_scheduler())
    logger.info("[Lifespan] Scheduler started")
    yield
    scheduler_task.cancel()
    logger.info("[Lifespan] Scheduler stopped")


app = FastAPI(
    title="Alpha-K Trading API",
    description="Professional Multi-Agent Swing Trading System API",
    version="1.0.0",
    lifespan=lifespan,
)

class AnalysisRequest(BaseModel):
    tickers: Optional[List[str]] = None
    balance: float = 100_000_000.0
    force_analysis: bool = False


class AnalysisResponse(BaseModel):
    report: str
    status: str
    timestamp: str
    phase: str

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Alpha-K"}

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze(req: AnalysisRequest):
    """
    Alpha-K 파이프라인을 실행합니다.
    - tickers가 있으면 해당 종목들만 정밀 분석합니다 (Phase 3부터).
    - tickers가 없으면 전체 시장 스크리닝부터 시작합니다 (Full Pipeline).
    """
    logger.info(f"Received analysis request: tickers={req.tickers}, balance={req.balance}")
    
    # Update risk agent balance
    risk_agent.account_balance = req.balance

    # ─── Build Initial State ───
    initial_state = {
        "market_regime": None,
        "top_sectors": None,
        "candidate_tickers": req.tickers,
        "technical_results": None,
        "fundamental_results": None,
        "flow_results": None,
        "scored_candidates": None,
        "final_tickers": None,
        "trade_plans": None,
        "report": "",
        "current_phase": "init",
        "error": None,
        "force_analysis": req.force_analysis,
    }


    try:
        if req.tickers:
            # ─── Direct Analysis Mode: Skip Phase 1 & 2 ───
            logger.info(f"Starting Direct Analysis for: {req.tickers}")
            state = dict(initial_state)
            
            # 여전히 시장 정보는 가져옴 (보고서용)
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
            # ─── Full Pipeline Mode ───
            logger.info("Starting Full Pipeline via LangGraph")
            final_state = graph.invoke(initial_state)

        report = final_state.get("report", "")
        if not report:
            report = "No report generated (market might be in CRASH/BEAR mode)."

        return AnalysisResponse(
            report=report,
            status="success",
            timestamp=datetime.now().isoformat(),
            phase=final_state.get("current_phase", "done")
        )
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        return AnalysisResponse(
            report=f"Analysis failed: {str(e)}",
            status="error",
            timestamp=datetime.now().isoformat(),
            phase="error"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
