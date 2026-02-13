"""
Event Service (GraphRAG)
========================
Neo4j를 사용하여 뉴스/공시 이벤트 노드를 관리하고,
이벤트와 기업/섹터/테마 간의 관계를 통해 파급효과(Impact)를 분석한다.
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from .neo4j_client import graph_client

class EventService:
    def __init__(self):
        self.client = graph_client

    def create_event(self, summary: str, sentiment_score: float, date: str, embedding: List[float] = None) -> str:
        """
        이벤트 노드 생성 (:Event)
        Returns: event_id (uuid)
        """
        query = """
        CREATE (e:Event {
            summary: $summary,
            sentiment_score: $sentiment,
            date: date($date),
            created_at: datetime(),
            embedding: $embedding
        })
        RETURN elementId(e) as id
        """
        params = {
            "summary": summary,
            "sentiment": sentiment_score,
            "date": date,
            "embedding": embedding or []
        }
        result = self.client.run_query(query, params)
        return result[0]['id'] if result else None

    def link_event_to_entity(self, event_id: str, identifier: str, relationship_type: str = "MENTIONS"):
        """
        이벤트와 엔티티(Ticker, Sector, Theme) 연결
        identifier: Ticker symbol, Sector code, or Theme name
        relationship_type: MENTIONS, AFFECTS, TRIGGERS
        """
        # Ticker
        query = f"""
        MATCH (e:Event) WHERE elementId(e) = $eid
        MATCH (t:Ticker {{ticker: $id}})
        MERGE (e)-[:{relationship_type}]->(t)
        """
        self.client.run_query(query, {"eid": event_id, "id": identifier})
        
        # Sector
        self.client.run_query(f"""
        MATCH (e:Event) WHERE elementId(e) = $eid
        MATCH (s:Sector {{sector_code: $id}})
        MERGE (e)-[:{relationship_type}]->(s)
        """, {"eid": event_id, "id": identifier})

        # Theme
        self.client.run_query(f"""
        MATCH (e:Event) WHERE elementId(e) = $eid
        MATCH (th:Theme {{theme_name: $id}})
        MERGE (e)-[:{relationship_type}]->(th)
        """, {"eid": event_id, "id": identifier})

    def get_ticker_impact(self, ticker: str, current_date: str = None, days: int = 7) -> float:
        """
        특정 종목에 대한 최근 이벤트 파급력 합계.
        Time-Travel 지원: current_date 기준 과거 days일 간의 이벤트만 조회.
        """
        if not current_date:
            current_date = datetime.now().strftime("%Y-%m-%d")

        fetch_query = """
        // 1. Direct
        MATCH (t:Ticker {ticker: $ticker})
        OPTIONAL MATCH (e1:Event)-[:MENTIONS]->(t)
        WHERE e1.date >= date($date) - duration({days: $days}) AND e1.date <= date($date)
        RETURN 'direct' as type, e1.sentiment_score as score
        
        UNION ALL
        
        // 2. Supply Chain (Supplier)
        MATCH (t:Ticker {ticker: $ticker})
        OPTIONAL MATCH (e2:Event)-[:MENTIONS]->(s:Ticker)-[:SUPPLIES_TO]->(t)
        WHERE e2.date >= date($date) - duration({days: $days}) AND e2.date <= date($date)
        RETURN 'supplier' as type, e2.sentiment_score as score
        
        UNION ALL
        
        // 3. Theme
        MATCH (t:Ticker {ticker: $ticker})
        OPTIONAL MATCH (e3:Event)-[:TRIGGERS]->(th:Theme)<-[:IN_THEME]-(t)
        WHERE e3.date >= date($date) - duration({days: $days}) AND e3.date <= date($date)
        RETURN 'theme' as type, e3.sentiment_score as score
        """
        
        results = self.client.run_query(fetch_query, {"ticker": ticker, "days": days, "date": current_date})
        
        total_score = 0.0
        for r in results:
            score = float(r.get('score') or 0)
            if r['type'] == 'direct':
                total_score += score * 1.0
            elif r['type'] == 'supplier':
                total_score += score * 0.5
            elif r['type'] == 'theme':
                total_score += score * 0.3
                
        return total_score

    def get_theme_impact(self, theme_name: str, current_date: str = None, days: int = 7) -> float:
        """
        테마에 대한 최근 이벤트 파급력.
        """
        if not current_date:
            current_date = datetime.now().strftime("%Y-%m-%d")
            
        query = """
        MATCH (th:Theme {theme_name: $theme})
        OPTIONAL MATCH (e:Event)-[:TRIGGERS]->(th)
        WHERE e.date >= date($date) - duration({days: $days}) AND e.date <= date($date)
        RETURN sum(e.sentiment_score) as total_impact
        """
        results = self.client.run_query(query, {"theme": theme_name, "days": days, "date": current_date})
        return float(results[0]['total_impact'] or 0.0) if results else 0.0

event_service = EventService()
