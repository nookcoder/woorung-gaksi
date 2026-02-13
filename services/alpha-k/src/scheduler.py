"""
Alpha-K Scheduler
==================
컨테이너 시작 시 자동으로 데일리 배치 작업을 스케줄링한다.
FastAPI lifespan에서 호출되어 백그라운드에서 동작.

스케줄:
  - 매일 18:00 KST: OHLCV 일봉 갱신 (KIS API)
  - 매일 18:10 KST: 투자자별 매매동향 + 업종 지수 수집
  - 매일 09:00 KST: 뉴스 크롤링 + 감성 분석
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Tuple

logger = logging.getLogger("alpha-k.scheduler")

KST = timezone(timedelta(hours=9))


class Job:
    """스케줄 작업 정의."""

    def __init__(self, name: str, func: Callable, hour: int, minute: int = 0):
        self.name = name
        self.func = func
        self.hour = hour
        self.minute = minute
        self.last_run = None

    def should_run(self, now: datetime) -> bool:
        """지금 실행해야 하는지 확인."""
        if now.hour == self.hour and now.minute == self.minute:
            # 같은 분에 중복 실행 방지
            if self.last_run and self.last_run.date() == now.date() and self.last_run.hour == self.hour:
                return False
            return True
        return False

    def run(self):
        """작업 실행 (동기)."""
        try:
            logger.info(f"[Scheduler] ▶ Starting: {self.name}")
            self.func()
            self.last_run = datetime.now(KST)
            logger.info(f"[Scheduler] ✅ Completed: {self.name}")
        except Exception as e:
            logger.error(f"[Scheduler] ❌ Failed: {self.name} → {e}")


# ─── Job 함수 정의 ───

def job_daily_ohlcv():
    """OHLCV 일봉 갱신 (최근 5일)."""
    from src.collector.market_data_collector import MarketDataCollector
    collector = MarketDataCollector()
    collector.update_daily_ohlcv_batch()


def job_investor_trading():
    """투자자별 매매동향 + 업종 지수 수집."""
    from src.collector.investor_trading_collector import InvestorTradingCollector
    collector = InvestorTradingCollector()
    tickers = collector._get_active_tickers()
    if tickers:
        collector.collect_investor_trading(tickers, label="daily")
        collector.collect_sector_indices()


def job_news_sentiment():
    """뉴스 크롤링 + 감성 분석."""
    from src.collector.news.news_crawler import NewsCrawler
    crawler = NewsCrawler()
    crawler.crawl_all()

    from src.agents.sentiment_analyzer import SentimentAnalyzer
    analyzer = SentimentAnalyzer()
    analyzer.run()


# ─── 스케줄 등록 ───

JOBS: List[Job] = [
    Job("Daily OHLCV Update", job_daily_ohlcv, hour=18, minute=0),
    Job("Investor Trading + Sector Index", job_investor_trading, hour=18, minute=10),
    Job("News Crawl + Sentiment", job_news_sentiment, hour=9, minute=0),
]


async def run_scheduler():
    """
    매 30초마다 현재 시각을 확인하고, 해당 시각의 작업을 실행.
    asyncio.to_thread로 동기 작업을 논블로킹 실행.
    """
    logger.info(f"[Scheduler] 🕐 Started. {len(JOBS)} jobs registered:")
    for j in JOBS:
        logger.info(f"  - {j.name} @ {j.hour:02d}:{j.minute:02d} KST")

    while True:
        now = datetime.now(KST)

        for job in JOBS:
            if job.should_run(now):
                # 동기 함수를 별도 쓰레드에서 실행 (API 서버 블로킹 방지)
                asyncio.create_task(asyncio.to_thread(job.run))

        await asyncio.sleep(30)  # 30초 간격 체크
