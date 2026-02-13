# Alpha-K V2 User Guide

=======================

이 문서는 Alpha-K V2에 추가된 **Backtesting System**과 **GraphRAG Reasoning System**의 사용 방법을 안내합니다.

## 1. Backtesting System (Time-Travel)

Alpha-K 에이전트 파이프라인이 과거 특정 시점에서 올바른 판단을 내리는지 검증하기 위한 시뮬레이션 환경입니다.

### 1.1 구성 요소

- `TimeMachineProvider`: 현재 날짜(`current_date`)를 설정하면, 그 이후의 데이터를 숨기고 과거 데이터만 리턴합니다.
- `VirtualBroker`: 에이전트의 `TradePlan`을 접수하여 가상 매매를 체결하고 수익률을 계산합니다.
- `BacktestRunner`: 날짜를 하루씩 넘기며 시뮬레이션을 수행하는 메인 루프입니다.

### 1.2 실행 방법

프로젝트 루트에서 다음 명령어를 실행합니다. (데이터베이스 연결 설정 필요)

```bash
# PYTHONPATH 설정 (필요시)
export PYTHONPATH=$PYTHONPATH:.

# 백테스트 실행 (기본 기간: 2024-01-01 ~ 2024-01-31)
python -m services.alpha_k.src.backtester.runner
```

### 1.3 주의사항

- **데이터 준비:** TimescaleDB에 해당 기간의 OHLCV 데이터가 적재되어 있어야 합니다.
- **성능:** 에이전트 파이프라인(LangGraph)을 매일 실행하므로 속도가 느릴 수 있습니다. 초기에는 짧은 기간(1주일)으로 테스트하세요.
- **Mocking:** `runner.py` 내에서 `supervisor.graph` 모듈의 `data_provider`를 `TimeMachineProvider`로 교체하는 코드가 포함되어 있습니다.

---

## 2. GraphRAG Reasoning System

뉴스 및 공시 데이터를 Neo4j 그래프에 연결하여, 단순 텍스트 검색을 넘어선 **파급력(Impact) 분석**을 수행합니다.

### 2.1 데이터 적재 (Sentiment Analysis)

`SentimentAnalyzer`는 ES에 수집된 뉴스를 분석하여 Neo4j에 `:Event` 노드를 생성합니다.

```python
from services.alpha_k.src.agents.sentiment_analyzer import SentimentAnalyzer

analyzer = SentimentAnalyzer()
analyzer.run_analysis(limit=100) # 분석할 뉴스 개수
```

위 코드를 실행하면:

1. LLM이 뉴스 감성 분석 (-1.0 ~ +1.0)
2. 중요 이벤트(점수 0.3 이상)는 Neo4j에 저장
3. `:MENTIONS` 관계 생성 (Event -> Ticker)

### 2.2 활용 (Agents)

GraphRAG 데이터는 에이전트가 자동으로 활용합니다.

- **SectorAgent**: 테마 분석 시, 최근 호재 뉴스(`Impact > 0`)가 많은 테마에 가산점을 부여합니다.
- **RiskAgent**: 공급망 리스크 분석 시, 공급사/고객사에 악재 뉴스(`Impact < -0.3`)가 발생했는지 확인합니다.

### 2.3 Neo4j 데이터 확인

Neo4j Browser에서 다음 쿼리로 이벤트 연결 상태를 확인할 수 있습니다.

```cypher
// 특정 종목에 영향을 미친 최근 이벤트 조회
MATCH (e:Event)-[:MENTIONS]->(t:Ticker {ticker: '005930'})
RETURN e.date, e.summary, e.sentiment_score
ORDER BY e.date DESC
LIMIT 10
```

---

## 3. 환경 설정

`.env` 파일에 다음 설정이 올바르게 되어 있는지 확인하세요.

```ini
# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# TimescaleDB (PostgreSQL)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=alphak
DB_USER=postgres
DB_PASSWORD=your_password

# LLM
OPENAI_API_KEY=sk-... (or DeepSeek key)
```
