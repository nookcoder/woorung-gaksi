# Alpha-K Architecture V2: Intelligence & Validation

**Date:** 2026-02-13
**Author:** Antigravity Agent
**Status:** Proposal

## 1. 개요 (Overview)

현재 Alpha-K 시스템은 **데이터 기반의 에이전트 실행 환경(Infrastructure V1)**을 갖추었습니다.
V2 고도화의 핵심 목표는 두 가지입니다.

1. **검증(Validation):** 5-Phase 에이전트 파이프라인이 과거 데이터에서 실제로 수익을 낼 수 있는지 검증하는 **Time-Travel Backtesting System**.
2. **지능화(Intelligence):** 단순 데이터 조회를 넘어, 뉴스/이벤트의 파급력을 그래프 기반으로 추론하는 **GraphRAG Reasoning System**.

---

## 2. Agent-based Backtesting System (Time-Travel)

기존 벡터 백테스터(`engine.py`)는 단일 전략 검증용입니다. 복잡한 에이전트 상호작용을 검증하기 위해 **Time-Travel 시뮬레이션**이 필요합니다.

### 2.1. 아키텍처

```mermaid
graph TD
    A[Simulation Loop] -->|Set Date (T)| B[Time Machine Provider]
    B -->|Historical Data at T| C[Alpha-K Agents]
    C -->|Trade Plan| D[Virtual Broker]
    D -->|Fill Orders| E[Portfolio & PnL]
    A -->|Next Day (T+1)| A
```

### 2.2. 핵심 컴포넌트

1.  **Time Machine Provider (`mock_provider.py`)**:
    - `MarketDataProvider`를 상속.
    - `set_current_date(date)` 메서드로 시뮬레이션 시점 설정.
    - 모든 데이터 요청 (`get_ohlcv`, `get_financials`)에 대해 **해당 시점 이전의 데이터만** 반환하여 Look-ahead Bias 방지.
    - Neo4j 데이터도 시점 필터링 필요 (생성일 기준).

2.  **Virtual Broker (`virtual_broker.py`)**:
    - `RiskAgent`가 생성한 `TradePlan`을 수신.
    - 주문 실행 로직:
      - **Market Buy:** 다음날 시가(Open) 진입 (슬리피지 적용).
      - **Limit Buy:** 다음날 저가(Low) <= 주문가 <= 고가(High) 시 체결.
      - **Stop Loss:** 장중 저가(Low)가 Stop 가격 건드리면 청산.
    - 자산(Cash/Equity) 및 포지션 관리.

3.  **Result Analyzer**:
    - 에이전트 로그(Thought Process)와 매매 결과를 매칭하여 분석.
    - 예: "TechnicalAgent가 VCP라고 판단했을 때의 승률은?"

---

## 3. GraphRAG Reasoning System (Neo4j 고도화)

현재 그래프(테마, 공급망)는 정적입니다. 여기에 **동적 이벤트(뉴스, 공시)**를 결합하여 에이전트의 상황 인지 능력을 극대화합니다.

### 3.1. 데이터 모델 확장

- **New Node Label:** `:Event` (News, Disclosure, MacroEvent)
  - Properties: `summary`, `sentiment_score`, `embedding`, `date`
- **New Relationships:**
  - `(:Event)-[:MENTIONS]->(:Ticker)`
  - `(:Event)-[:AFFECTS]->(:Sector)`
  - `(:Event)-[:TRIGGERS]->(:Theme)`

### 3.2. GraphRAG 프로세스

1.  **News Ingestion (OpenClaw 연동):**
    - OpenClaw가 수집한 뉴스를 LLM이 요약 및 임베딩.
    - Neo4j에 `:Event` 노드 생성 및 관련 키워드(종목/테마) 자동 연결.

2.  **Impact Propagation (파급력 전파):**
    - 이벤트 발생 시 연결된 노드로 영향력 전파 시뮬레이션.
    - **Logic:** `Event(Sentiment +0.8)` -> `SupplyChain(Customer)` -> `Supplier(Impact +0.4)`
    - 공급망 리스크나 테마 호재가 2차, 3차 관계 기업에 미칠 영향 예측.

3.  **Agent Integration:**
    - **SectorAgent:** "최근 3일간 긍정적 이벤트가 가장 많이 연결된 테마는?"
    - **RiskAgent:** "보유 종목의 공급망에 악재 이벤트가 발생했는가?"

---

## 4. Implementation Roadmap

### Phase 2.1: Time-Travel Backtester 구축 (우선순위 높음)

에이전트 로직의 유효성을 검증하는 것이 시급함.

1.  `src/backtester/time_machine.py`: Mock Provider 구현.
2.  `src/backtester/virtual_broker.py`: 가상 브로커 구현.
3.  `src/backtester/runner.py`: 시뮬레이션 루프 구현.

### Phase 2.2: GraphRAG 데이터 파이프라인

1.  Neo4j Schema 업데이트 (`:Event` 노드 추가).
2.  `src/infrastructure/graph/event_service.py`: 이벤트 주입 및 조회 서비스.
3.  OpenClaw -> Alpha-K 뉴스 데이터 연동 파이프라인.

### Phase 2.3: 에이전트 지능화 (GraphRAG 적용)

1.  `SentimentAnalyzer` 리팩토링: 단순 텍스트 분석 -> 그래프 기반 파급력 분석.
2.  `SectorAgent`, `RiskAgent`에 Graph Query 로직 추가.
