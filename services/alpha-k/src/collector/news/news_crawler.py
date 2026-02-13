"""
News Crawler for Alpha-K (Google News RSS)
==========================================
Google News RSS를 사용하여 종목별 최신 뉴스를 수집하고 Elasticsearch에 적재한다.

장점:
- JavaScript 렌더링 불필요 (RSS = XML)
- Rate Limit이 느슨함
- 다양한 언론사 뉴스를 한번에 수집 가능
"""
import time
import requests
import logging
import hashlib
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

from ...infrastructure.db.db_client import db_client
from ...infrastructure.es.es_client import es_client, ESClient

logger = logging.getLogger(__name__)


class NewsCrawler:
    """Google News RSS 기반 뉴스 크롤러."""

    GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"

    def __init__(self):
        self.db = db_client
        self.es = es_client
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        self.DELAY = 1.0  # Google RSS Rate Limit 준수

    def run_daily_crawl(self, limit: int = None):
        """
        활성 종목들에 대해 최신 뉴스를 수집한다.
        """
        logger.info("[NewsCrawler] Starting daily news crawl...")

        try:
            # 1. Get active tickers with names (뉴스 검색은 종목명으로)
            active_tickers = self.db.fetch_all(
                "SELECT ticker_code, ticker_name FROM tickers WHERE is_active = TRUE ORDER BY ticker_code"
            )
            if not active_tickers:
                logger.warning("[NewsCrawler] No active tickers found.")
                return

            tickers = active_tickers
            if limit:
                tickers = tickers[:limit]

            logger.info(f"[NewsCrawler] Target: {len(tickers)} tickers")

            total_indexed = 0
            for i, (code, name) in enumerate(tickers):
                try:
                    news_list = self._crawl_google_news(code, name)

                    if news_list:
                        indexed_cnt = self._save_to_es(news_list)
                        total_indexed += indexed_cnt

                    time.sleep(self.DELAY)

                    if (i + 1) % 50 == 0:
                        logger.info(
                            f"[NewsCrawler] Progress: {i+1}/{len(tickers)} tickers. "
                            f"Total indexed: {total_indexed}"
                        )

                except Exception as e:
                    logger.error(f"[NewsCrawler] Failed for {code} ({name}): {e}")

            logger.info(f"[NewsCrawler] Completed. Total indexed: {total_indexed}")

        except Exception as e:
            logger.error(f"[NewsCrawler] Daily crawl failed: {e}")

    def _crawl_google_news(self, ticker_code: str, ticker_name: str) -> List[Dict]:
        """
        Google News RSS에서 종목명으로 검색하여 최근 24시간 뉴스를 가져온다.
        """
        query = urllib.parse.quote(ticker_name)
        url = f"{self.GOOGLE_NEWS_RSS}?q={query}&hl=ko&gl=KR&ceid=KR:ko"

        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.content, "xml")
            items = soup.select("item")

            if not items:
                return []

            articles = []
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

            for item in items:
                try:
                    title = item.select_one("title").text if item.select_one("title") else ""
                    link = item.select_one("link")
                    # BeautifulSoup XML에서 <link>는 .next_sibling으로 텍스트를 가져와야 할 수 있음
                    if link:
                        link_text = link.text if link.text else link.next_sibling
                        if not link_text or not str(link_text).startswith("http"):
                            link_text = ""
                    else:
                        link_text = ""
                    
                    pub_date_str = item.select_one("pubDate").text if item.select_one("pubDate") else ""
                    source = item.select_one("source").text if item.select_one("source") else "Unknown"

                    # Parse date
                    if pub_date_str:
                        pub_date = parsedate_to_datetime(pub_date_str)
                    else:
                        continue

                    # 24시간 필터
                    if pub_date < cutoff:
                        continue

                    # Stable doc ID for deduplication
                    doc_id = hashlib.sha256(f"{ticker_code}_{link_text}".encode()).hexdigest()

                    articles.append({
                        "id": doc_id,
                        "ticker_code": ticker_code,
                        "title": title,
                        "url": str(link_text).strip(),
                        "source": source,
                        "published_at": pub_date.isoformat(),
                        "content": title,  # 본문 크롤링은 추후 확장
                    })

                except Exception as e:
                    logger.debug(f"[NewsCrawler] Skipping item: {e}")
                    continue

            return articles

        except Exception as e:
            logger.warning(f"[NewsCrawler] RSS error {ticker_code} ({ticker_name}): {e}")
            return []

    def _save_to_es(self, news_list: List[Dict]) -> int:
        """Elasticsearch에 뉴스 문서를 저장한다."""
        count = 0
        for news in news_list:
            doc_id = news.pop("id")
            try:
                self.es.index_document(ESClient.INDEX_NEWS, doc_id, news)
                count += 1
            except Exception as e:
                logger.error(f"[NewsCrawler] ES index failed: {e}")
        return count


# Entry Point for Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    crawler = NewsCrawler()
    crawler.run_daily_crawl(limit=5)  # Test 5 tickers
