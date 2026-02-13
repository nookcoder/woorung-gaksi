"""
Historical OHLCV Backfill Script (One-time)
============================================
분석 정확도를 높이기 위해 과거 3년치 OHLCV 데이터를 TimescaleDB에 적재한다.
FinanceDataReader를 사용하여 KIS API Rate Limit 없이 대량 수집.

Usage:
    docker exec woorung-alpha-k python3 -m src.collector.backfill_historical
"""
import time
import logging
import pandas as pd
import FinanceDataReader as fdr
from datetime import datetime

from ..infrastructure.db.db_client import db_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ─── Config ───
START_DATE = "2023-02-13"
END_DATE = "2026-02-13"
BATCH_DELAY = 0.3       # FDR 요청 간 0.3초 대기 (네이버 차단 방지)
COMMIT_BATCH = 50        # 50종목마다 DB 커밋 로그


def backfill():
    db = db_client

    # 1. 활성 종목 조회
    rows = db.fetch_all(
        "SELECT ticker_code, ticker_name FROM tickers WHERE is_active = TRUE ORDER BY ticker_code"
    )
    if not rows:
        logger.error("활성 종목이 없습니다. 먼저 update_master()를 실행하세요.")
        return

    tickers = [(r[0], r[1]) for r in rows]
    total = len(tickers)
    logger.info(f"=== Backfill 시작: {total}종목, {START_DATE} ~ {END_DATE} ===")

    # 2. UPSERT 쿼리
    upsert_sql = """
    INSERT INTO ohlcv_daily (time, ticker_code, open, high, low, close, volume, change_rate)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (time, ticker_code) DO UPDATE SET
        open = EXCLUDED.open, high = EXCLUDED.high,
        low = EXCLUDED.low, close = EXCLUDED.close,
        volume = EXCLUDED.volume, change_rate = EXCLUDED.change_rate;
    """

    success = 0
    failed = 0
    total_rows = 0
    start_time = datetime.now()

    for idx, (code, name) in enumerate(tickers):
        try:
            df = fdr.DataReader(code, START_DATE, END_DATE)
            if df.empty:
                failed += 1
                continue

            # DB 저장
            with db.get_cursor() as cur:
                for date_idx, row in df.iterrows():
                    cur.execute(upsert_sql, (
                        date_idx,
                        code,
                        float(row["Open"]),
                        float(row["High"]),
                        float(row["Low"]),
                        float(row["Close"]),
                        int(row["Volume"]),
                        float(row.get("Change", 0)),
                    ))
                total_rows += len(df)

            success += 1

            # 진행률
            if (idx + 1) % COMMIT_BATCH == 0 or (idx + 1) == total:
                elapsed = (datetime.now() - start_time).total_seconds()
                rate = (idx + 1) / elapsed if elapsed > 0 else 0
                eta = (total - idx - 1) / rate if rate > 0 else 0
                logger.info(
                    f"[{idx+1}/{total}] {code} {name} | "
                    f"rows={total_rows:,} | "
                    f"ok={success} fail={failed} | "
                    f"ETA: {int(eta//60)}m {int(eta%60)}s"
                )

            time.sleep(BATCH_DELAY)

        except Exception as e:
            failed += 1
            logger.warning(f"[{idx+1}/{total}] {code} {name} 실패: {e}")
            time.sleep(1)  # 에러 시 1초 대기
            continue

    elapsed_total = (datetime.now() - start_time).total_seconds()
    logger.info(
        f"\n=== Backfill 완료 ===\n"
        f"  종목: {success}/{total} 성공 ({failed} 실패)\n"
        f"  데이터: {total_rows:,} rows\n"
        f"  소요: {int(elapsed_total//60)}분 {int(elapsed_total%60)}초"
    )


if __name__ == "__main__":
    backfill()
