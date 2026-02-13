"""
Graph Service — Neo4j 비즈니스 로직 레이어
==========================================
Neo4j에 저장된 관계형 데이터를 에이전트가 활용할 수 있는
비즈니스 메서드로 제공한다.

기능:
  - 테마 → 종목 조회 (SectorAgent)
  - 종목 → 소속 테마 조회
  - 경쟁사 조회 (FundamentalAgent)
  - 공급망 조회 (RiskAgent)
  - 지배구조 조회
"""
import logging
from typing import Dict, List, Optional

from .neo4j_client import graph_client

logger = logging.getLogger(__name__)


class GraphService:
    """Neo4j 관계형 데이터를 에이전트에 제공하는 서비스 계층."""

    def __init__(self):
        self.client = graph_client

    @property
    def is_available(self) -> bool:
        return self.client.is_connected

    # ─────────────────────────────────────────────
    # Theme ↔ Ticker
    # ─────────────────────────────────────────────

    def get_all_themes(self) -> List[Dict]:
        """모든 테마와 소속 종목 수를 반환."""
        query = """
        MATCH (theme:Theme)<-[:BELONGS_TO]-(t:Ticker)
        RETURN theme.name AS theme_name,
               theme.category AS category,
               COUNT(t) AS ticker_count
        ORDER BY ticker_count DESC
        """
        return self.client.run_query(query)

    def get_theme_tickers(self, theme_name: str) -> List[Dict]:
        """특정 테마에 속한 종목 리스트 반환."""
        query = """
        MATCH (t:Ticker)-[:BELONGS_TO]->(theme:Theme {name: $theme_name})
        RETURN t.code AS ticker_code, t.name AS ticker_name
        ORDER BY t.name
        """
        return self.client.run_query(query, {"theme_name": theme_name})

    def get_top_themes_with_tickers(self, limit: int = 10) -> List[Dict]:
        """종목 수 기준 상위 테마와 그 종목 리스트 반환."""
        query = """
        MATCH (t:Ticker)-[:BELONGS_TO]->(theme:Theme)
        WITH theme, COLLECT({code: t.code, name: t.name}) AS tickers,
             COUNT(t) AS cnt
        ORDER BY cnt DESC
        LIMIT $limit
        RETURN theme.name AS theme_name,
               theme.category AS category,
               tickers, cnt AS ticker_count
        """
        return self.client.run_query(query, {"limit": limit})

    def get_ticker_themes(self, ticker_code: str) -> List[str]:
        """종목이 속한 모든 테마 이름 반환."""
        query = """
        MATCH (t:Ticker {code: $code})-[:BELONGS_TO]->(theme:Theme)
        RETURN theme.name AS theme_name
        """
        results = self.client.run_query(query, {"code": ticker_code})
        return [r["theme_name"] for r in results]

    def get_theme_peers(self, ticker_code: str) -> List[Dict]:
        """같은 테마에 속한 다른 종목(동료 종목) 반환."""
        query = """
        MATCH (t:Ticker {code: $code})-[:BELONGS_TO]->(theme:Theme)<-[:BELONGS_TO]-(peer:Ticker)
        WHERE peer.code <> $code
        RETURN DISTINCT peer.code AS ticker_code, peer.name AS ticker_name,
               COLLECT(DISTINCT theme.name) AS shared_themes
        ORDER BY SIZE(shared_themes) DESC
        """
        return self.client.run_query(query, {"code": ticker_code})

    # ─────────────────────────────────────────────
    # Competitors
    # ─────────────────────────────────────────────

    def get_competitors(self, ticker_code: str) -> List[Dict]:
        """종목의 경쟁사 리스트 반환 (도메인 포함)."""
        query = """
        MATCH (t:Ticker {code: $code})-[r:COMPETES_WITH]-(comp:Ticker)
        RETURN comp.code AS ticker_code, comp.name AS ticker_name,
               r.domain AS domain
        """
        return self.client.run_query(query, {"code": ticker_code})

    # ─────────────────────────────────────────────
    # Supply Chain
    # ─────────────────────────────────────────────

    def get_suppliers(self, ticker_code: str) -> List[Dict]:
        """이 종목에 공급하는 업체 리스트."""
        query = """
        MATCH (supplier:Ticker)-[r:SUPPLIES_TO]->(t:Ticker {code: $code})
        RETURN supplier.code AS ticker_code, supplier.name AS ticker_name,
               r.product AS product
        """
        return self.client.run_query(query, {"code": ticker_code})

    def get_customers(self, ticker_code: str) -> List[Dict]:
        """이 종목이 공급하는 고객사 리스트."""
        query = """
        MATCH (t:Ticker {code: $code})-[r:SUPPLIES_TO]->(customer:Ticker)
        RETURN customer.code AS ticker_code, customer.name AS ticker_name,
               r.product AS product
        """
        return self.client.run_query(query, {"code": ticker_code})

    def get_full_supply_chain(self, ticker_code: str) -> Dict:
        """상위(공급자) + 하위(고객사) 전체 공급망 반환."""
        return {
            "suppliers": self.get_suppliers(ticker_code),
            "customers": self.get_customers(ticker_code),
        }

    def get_supply_chain_risk(self, ticker_code: str) -> List[Dict]:
        """공급망 내 연결된 모든 종목 (2-hop depth)."""
        query = """
        MATCH path = (t:Ticker {code: $code})-[:SUPPLIES_TO*1..2]-(related:Ticker)
        WHERE related.code <> $code
        RETURN DISTINCT related.code AS ticker_code, related.name AS ticker_name,
               LENGTH(path) AS depth
        ORDER BY depth
        """
        return self.client.run_query(query, {"code": ticker_code})

    # ─────────────────────────────────────────────
    # Ownership / Group Structure
    # ─────────────────────────────────────────────

    def get_subsidiaries(self, company_name: str) -> List[Dict]:
        """그룹사의 자회사 종목 리스트."""
        query = """
        MATCH (parent:Company {name: $name})<-[:SUBSIDIARY_OF]-(child)
        OPTIONAL MATCH (child)<-[:IS_TICKER]-(ticker:Ticker)
        RETURN child.name AS subsidiary_name,
               ticker.code AS ticker_code,
               ticker.name AS ticker_name
        """
        return self.client.run_query(query, {"name": company_name})

    def get_parent_company(self, ticker_code: str) -> Optional[Dict]:
        """종목의 모회사/그룹 반환."""
        query = """
        MATCH (t:Ticker {code: $code})-[:IS_TICKER]->(c:Company)-[:SUBSIDIARY_OF]->(parent:Company)
        RETURN parent.name AS parent_name, c.name AS company_name
        """
        results = self.client.run_query(query, {"code": ticker_code})
        return results[0] if results else None

    def get_group_tickers(self, ticker_code: str) -> List[Dict]:
        """같은 그룹에 속한 다른 종목 리스트."""
        query = """
        MATCH (t:Ticker {code: $code})-[:IS_TICKER]->(c:Company)-[:SUBSIDIARY_OF]->(parent:Company)
        MATCH (parent)<-[:SUBSIDIARY_OF]-(sibling:Company)<-[:IS_TICKER]-(peer:Ticker)
        WHERE peer.code <> $code
        RETURN DISTINCT peer.code AS ticker_code, peer.name AS ticker_name,
               sibling.name AS company_name
        """
        return self.client.run_query(query, {"code": ticker_code})

    # ─────────────────────────────────────────────
    # Advanced Queries (for Agents)
    # ─────────────────────────────────────────────

    def get_theme_momentum_candidates(self, theme_name: str) -> List[str]:
        """특정 테마의 종목 코드만 리스트로 반환 (분석용)."""
        tickers = self.get_theme_tickers(theme_name)
        return [t["ticker_code"] for t in tickers]

    def get_related_tickers_all(self, ticker_code: str) -> Dict:
        """종목과 관계있는 모든 종목을 관계 유형별로 반환."""
        return {
            "themes": self.get_ticker_themes(ticker_code),
            "theme_peers": self.get_theme_peers(ticker_code),
            "competitors": self.get_competitors(ticker_code),
            "supply_chain": self.get_full_supply_chain(ticker_code),
            "group_peers": self.get_group_tickers(ticker_code),
        }

    def search_theme(self, keyword: str) -> List[Dict]:
        """키워드로 테마 검색 (부분 일치)."""
        query = """
        MATCH (theme:Theme)
        WHERE theme.name CONTAINS $keyword
        RETURN theme.name AS theme_name, theme.category AS category
        """
        return self.client.run_query(query, {"keyword": keyword})


# Singleton instance
graph_service = GraphService()
