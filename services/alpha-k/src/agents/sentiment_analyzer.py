"""
Sentiment Analyzer (LLM-based)
==============================
Elasticsearch에 저장된 뉴스 제목을 LLM(DeepSeek)에게 보내
감성 점수(-1.0 ~ +1.0)와 영향 기간을 분석한 뒤, ES 문서를 업데이트한다.

Flow:
1. ES에서 아직 sentiment_score가 없는 뉴스 조회
2. 뉴스를 배치(Batch)로 묶어 LLM에 전달
3. LLM의 응답(JSON)을 파싱하여 ES 문서를 업데이트
"""
import json
import logging
from typing import List, Dict, Optional

from ..infrastructure.es.es_client import es_client, ESClient
from ..infrastructure.llm_client import llm_client

logger = logging.getLogger(__name__)

SENTIMENT_PROMPT = """당신은 한국 주식시장 전문 뉴스 감성 분석가입니다.
아래 뉴스 제목 목록을 분석하여 각 뉴스가 해당 종목의 **주가에 미치는 영향**을 평가하세요.

## 규칙
1. 각 뉴스에 대해 다음을 JSON 배열로 반환하세요:
   - "index": 뉴스 번호 (0부터)
   - "score": -1.0(극도로 부정적) ~ +1.0(극도로 긍정적) 사이의 실수
   - "impact": "SHORT"(1~3일), "MID"(1주~1달), "LONG"(3개월 이상) 중 하나
   - "reason": 판단 근거 (한국어, 20자 이내)

2. 점수 기준:
   - +0.8 ~ +1.0: 대형 호재 (실적 서프라이즈, 대규모 수주, 정부 정책 수혜)
   - +0.3 ~ +0.7: 소규모 호재 (신제품 출시, 협력 확대)
   - -0.2 ~ +0.2: 중립 (일반 기사, 인사 발령, 주주총회)
   - -0.7 ~ -0.3: 소규모 악재 (실적 하락, 경쟁 심화)
   - -1.0 ~ -0.8: 대형 악재 (횡령, 대규모 리콜, 상장폐지 위험)

3. 반드시 유효한 JSON 배열만 출력하세요. 다른 텍스트는 포함하지 마세요.

## 뉴스 목록
{news_list}

## 응답 (JSON 배열만)
"""


class SentimentAnalyzer:
    """LLM 기반 뉴스 감성 분석기."""

    BATCH_SIZE = 20  # 한 번에 분석할 뉴스 수

    def __init__(self):
        self.es = es_client
        self.llm = llm_client.get_agent_llm("sentiment")

    def run_analysis(self, limit: int = None):
        """
        ES에서 분석되지 않은 뉴스를 가져와 감성 점수를 매긴다.
        """
        logger.info("[SentimentAnalyzer] Starting sentiment analysis...")

        if not self.llm:
            logger.error("[SentimentAnalyzer] LLM not available. Check config.")
            return

        # 1. ES에서 sentiment_score가 없는 뉴스 조회
        unscored_news = self._get_unscored_news(limit or 100)
        if not unscored_news:
            logger.info("[SentimentAnalyzer] No unscored news found.")
            return

        logger.info(f"[SentimentAnalyzer] Found {len(unscored_news)} unscored news.")

        # 2. 배치 처리
        total_scored = 0
        for i in range(0, len(unscored_news), self.BATCH_SIZE):
            batch = unscored_news[i : i + self.BATCH_SIZE]
            try:
                scored = self._analyze_batch(batch)
                total_scored += scored
                logger.info(
                    f"[SentimentAnalyzer] Batch {i // self.BATCH_SIZE + 1}: "
                    f"scored {scored}/{len(batch)}"
                )
            except Exception as e:
                logger.error(f"[SentimentAnalyzer] Batch failed: {e}")

        logger.info(f"[SentimentAnalyzer] Completed. Total scored: {total_scored}")

    def _get_unscored_news(self, limit: int) -> List[Dict]:
        """ES에서 sentiment_score 필드가 없는(= 분석 안 된) 뉴스를 가져온다."""
        query = {
            "query": {
                "bool": {
                    "must_not": [{"exists": {"field": "sentiment_score"}}]
                }
            },
            "sort": [{"published_at": {"order": "desc"}}],
            "size": limit,
        }

        try:
            results = self.es.client.search(index=ESClient.INDEX_NEWS, body=query)
            hits = results["hits"]["hits"]
            return [
                {
                    "doc_id": hit["_id"],
                    "ticker_code": hit["_source"].get("ticker_code", ""),
                    "title": hit["_source"].get("title", ""),
                }
                for hit in hits
            ]
        except Exception as e:
            logger.error(f"[SentimentAnalyzer] ES query failed: {e}")
            return []

    def _analyze_batch(self, batch: List[Dict]) -> int:
        """뉴스 배치를 LLM에게 보내 감성 분석을 수행한다."""
        # 뉴스 목록 포맷팅
        news_lines = []
        for i, news in enumerate(batch):
            news_lines.append(f"{i}. [{news['ticker_code']}] {news['title']}")

        news_text = "\n".join(news_lines)
        prompt = SENTIMENT_PROMPT.format(news_list=news_text)

        # LLM 호출
        try:
            response = self.llm.invoke(prompt)
            content = response.content.strip()

            # JSON 파싱 (```json ... ``` 래핑 제거)
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            results = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"[SentimentAnalyzer] JSON parse error: {e}")
            logger.debug(f"[SentimentAnalyzer] Raw response: {content[:500]}")
            return 0
        except Exception as e:
            logger.error(f"[SentimentAnalyzer] LLM call failed: {e}")
            return 0

        # 3. ES 문서 업데이트
        scored = 0
        for result in results:
            try:
                idx = result.get("index", -1)
                if 0 <= idx < len(batch):
                    doc_id = batch[idx]["doc_id"]
                    score = max(-1.0, min(1.0, float(result.get("score", 0))))
                    impact = result.get("impact", "SHORT")
                    reason = result.get("reason", "")

                    self.es.client.update(
                        index=ESClient.INDEX_NEWS,
                        id=doc_id,
                        body={
                            "doc": {
                                "sentiment_score": score,
                                "impact_duration": impact,
                                "sentiment_reason": reason,
                            }
                        },
                    )
                    scored += 1
            except Exception as e:
                logger.error(f"[SentimentAnalyzer] ES update failed: {e}")

        return scored


# Entry Point for Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analyzer = SentimentAnalyzer()
    analyzer.run_analysis(limit=20)
