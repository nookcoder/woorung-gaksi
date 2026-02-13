"""
Investor Trading Collector (Daily Batch + Backfill)
====================================================
KIS API를 사용하여 투자자별 매매동향(외인/기관/개인)을 수집하고 TimescaleDB에 적재.

데일리 배치:
    docker exec woorung-alpha-k python3 -m src.collector.investor_trading_collector daily

백필 (과거 데이터):
    docker exec woorung-alpha-k python3 -m src.collector.investor_trading_collector backfill

Note:
- KIS API `get_investor_trading()`은 종목별 최근 30거래일 데이터를 반환.
- Rate Limit: 초당 20건 → 0.06s 딜레이 적용.
- 백필은 30일치만 가능 (API 제한). 더 과거 데이터는 KIS API로 불가.
"""
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import List, Tuple

from ..infrastructure.data_providers.kis_client import KISClient
from ..infrastructure.db.db_client import db_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Config ───
API_DELAY = 0.06        # KIS Rate Limit (초당 20건)
SECTOR_CODES = {
    # KOSPI 주요 업종
    "0001": "종합(KOSPI)",
    "0002": "대형주",
    "0003": "중형주",
    "0004": "소형주",
    "0005": "음식료업",
    "0006": "섬유의복",
    "0007": "종이목재",
    "0008": "화학",
    "0009": "의약품",
    "0010": "비금속광물",
    "0011": "철강금속",
    "0012": "기계",
    "0013": "전기전자",
    "0014": "의료정밀",
    "0015": "운수장비",
    "0016": "유통업",
    "0017": "전기가스업",
    "0018": "건설업",
    "0019": "운수창고업",
    "0020": "통신업",
    "0021": "금융업",
    "0022": "은행",
    "0024": "증권",
    "0025": "보험",
    "0026": "서비스업",
    "0027": "제조업",
    # KOSDAQ
    "1001": "종합(KOSDAQ)",
    "2001": "KOSPI200",
}


class InvestorTradingCollector:
    """투자자별 매매동향 수집기."""

    def __init__(self):
        self.kis = KISClient()
        self.db = db_client

    # ─────────────────────────────────────────────
    # 1. 종목별 투자자 매매동향 수집
    # ─────────────────────────────────────────────

    def collect_investor_trading(self, tickers: List[Tuple[str, str]], label: str = "batch"):
        """
        종목별 투자자 매매동향을 KIS API로 수집하여 DB에 저장.
        KIS API는 종목당 최근 30거래일 데이터를 반환.
        """
        upsert_sql = """
        INSERT INTO investor_trading (
            time, ticker_code,
            foreigner_net_qty, institution_net_qty, individual_net_qty,
            foreigner_net_amt, institution_net_amt, individual_net_amt
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (time, ticker_code) DO UPDATE SET
            foreigner_net_qty = EXCLUDED.foreigner_net_qty,
            institution_net_qty = EXCLUDED.institution_net_qty,
            individual_net_qty = EXCLUDED.individual_net_qty,
            foreigner_net_amt = EXCLUDED.foreigner_net_amt,
            institution_net_amt = EXCLUDED.institution_net_amt,
            individual_net_amt = EXCLUDED.individual_net_amt;
        """

        total = len(tickers)
        success = 0
        failed = 0
        total_rows = 0
        start_time = datetime.now()

        for idx, (code, name) in enumerate(tickers):
            try:
                df = self.kis.get_investor_trading(code)
                time.sleep(API_DELAY)

                if df.empty:
                    failed += 1
                    continue

                with self.db.get_cursor() as cur:
                    for date_idx, row in df.iterrows():
                        cur.execute(upsert_sql, (
                            date_idx, code,
                            int(row.get("foreigner_net_qty", 0)),
                            int(row.get("institution_net_qty", 0)),
                            int(row.get("individual_net_qty", 0)),
                            int(row.get("foreigner_net_amt", 0)),
                            int(row.get("institution_net_amt", 0)),
                            int(row.get("individual_net_amt", 0)),
                        ))
                    total_rows += len(df)

                success += 1

                if (idx + 1) % 100 == 0 or (idx + 1) == total:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    rate = (idx + 1) / elapsed if elapsed > 0 else 0
                    eta = (total - idx - 1) / rate if rate > 0 else 0
                    logger.info(
                        f"[{label}] [{idx+1}/{total}] {code} {name} | "
                        f"rows={total_rows:,} | ok={success} fail={failed} | "
                        f"ETA: {int(eta//60)}m {int(eta%60)}s"
                    )

            except Exception as e:
                failed += 1
                logger.warning(f"[{label}] [{idx+1}/{total}] {code} {name} 실패: {e}")
                time.sleep(1)
                continue

        elapsed_total = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"\n=== [{label}] 완료 ===\n"
            f"  종목: {success}/{total} 성공 ({failed} 실패)\n"
            f"  데이터: {total_rows:,} rows\n"
            f"  소요: {int(elapsed_total//60)}분 {int(elapsed_total%60)}초"
        )

    # ─────────────────────────────────────────────
    # 2. 업종별 지수 수집
    # ─────────────────────────────────────────────

    def collect_sector_indices(self, start_date: str = None, end_date: str = None):
        """업종별 일간 지수를 수집하여 sector_indices 테이블에 저장."""
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

        upsert_sql = """
        INSERT INTO sector_indices (time, sector_code, sector_name, close, change_rate)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (time, sector_code) DO UPDATE SET
            sector_name = EXCLUDED.sector_name,
            close = EXCLUDED.close,
            change_rate = EXCLUDED.change_rate;
        """

        total_rows = 0

        for code, name in SECTOR_CODES.items():
            try:
                df = self.kis.get_sector_daily(code, start_date, end_date)
                time.sleep(API_DELAY)

                if df.empty:
                    logger.warning(f"[Sector] {code} {name}: 데이터 없음")
                    continue

                with self.db.get_cursor() as cur:
                    for date_idx, row in df.iterrows():
                        change_rate = 0
                        if "Close" in row and float(row["Close"]) > 0:
                            # 등락률은 API에서 직접 제공하지 않으므로 스킵 (0으로)
                            pass
                        cur.execute(upsert_sql, (
                            date_idx, code, name,
                            float(row.get("Close", 0)),
                            change_rate,
                        ))
                    total_rows += len(df)

                logger.info(f"[Sector] {code} {name}: {len(df)} rows")

            except Exception as e:
                logger.warning(f"[Sector] {code} {name} 실패: {e}")
                time.sleep(1)

        logger.info(f"[Sector] 완료. 총 {total_rows:,} rows")

    # ─────────────────────────────────────────────
    # Helper
    # ─────────────────────────────────────────────

    def _get_active_tickers(self, limit: int = None) -> List[Tuple[str, str]]:
        """DB에서 활성 종목 리스트 조회."""
        rows = self.db.fetch_all(
            "SELECT ticker_code, ticker_name FROM tickers WHERE is_active = TRUE ORDER BY ticker_code"
        )
        tickers = [(r[0], r[1]) for r in rows]
        if limit:
            tickers = tickers[:limit]
        return tickers


def daily_batch():
    """
    데일리 배치: 매일 크론에서 실행.
    - 활성 종목의 투자자별 매매동향 (최근 30일 → UPSERT)
    - 업종별 지수 (최근 30일)
    """
    logger.info("=== Daily Batch: 투자자 매매동향 + 업종 지수 ===")
    collector = InvestorTradingCollector()

    tickers = collector._get_active_tickers()
    if not tickers:
        logger.error("활성 종목 없음. update_master() 먼저 실행하세요.")
        return

    # 1. 투자자 매매동향
    collector.collect_investor_trading(tickers, label="daily")

    # 2. 업종별 지수
    collector.collect_sector_indices()


def backfill():
    """
    백필: 과거 데이터 일괄 적재 (일회성).
    - KIS API 제한: 종목별 최근 30거래일만 반환 → 30일치가 최대.
    - 2,771종목 × 0.06s = ~3분 소요 예상.
    - 업종 지수는 더 긴 기간 조회 가능 (100일+).
    """
    logger.info("=== Backfill: 투자자 매매동향 + 업종 지수 ===")
    collector = InvestorTradingCollector()

    tickers = collector._get_active_tickers()
    if not tickers:
        logger.error("활성 종목 없음. update_master() 먼저 실행하세요.")
        return

    logger.info(f"활성 종목: {len(tickers)}개")

    # 1. 투자자 매매동향 (최근 30거래일)
    collector.collect_investor_trading(tickers, label="backfill")

    # 2. 업종별 지수 (최근 1년)
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=365)
    collector.collect_sector_indices(
        start_date=start_dt.strftime("%Y%m%d"),
        end_date=end_dt.strftime("%Y%m%d"),
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        backfill()
    else:
        daily_batch()
