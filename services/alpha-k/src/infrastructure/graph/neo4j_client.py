"""
Neo4j Graph Client (Singleton)
===============================
Alpha-K 관계형 데이터를 위한 Neo4j 클라이언트.
테마(섹터) 구성, 공급망, 지분 관계, 경쟁사 관계를 그래프로 관리.

Usage:
    from src.infrastructure.graph.neo4j_client import graph_client
    graph_client.run_query("MATCH (t:Ticker) RETURN t LIMIT 5")
"""
import os
import logging
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Neo4j Graph Database 클라이언트 (Singleton)."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        uri: str = None,
        user: str = None,
        password: str = None,
    ):
        if self._initialized:
            return
        self._initialized = True

        self.uri = uri or os.getenv("NEO4J_URI")
        self.user = user or os.getenv("NEO4J_USER")
        self.password = password or os.getenv("NEO4J_PASSWORD")

        if not all([self.uri, self.user, self.password]):
            logger.warning("[Neo4j] Missing environment variables. Connection might fail.")
            # We don't raise here because Neo4j might be optional? 
            # But the user asked to "manage in env vars", implying strictness.
            # However, if Neo4j is critical, we should log error.
            # Let's align with DB client strictness but maybe just log error if it's optional feature.
            # Given it's "infrastructure", let's assume it should be configured if used.


        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            logger.info(f"[Neo4j] Connected to {self.uri}")
        except Exception as e:
            logger.error(f"[Neo4j] Connection failed: {e}")
            self.driver = None

    def close(self):
        if self.driver:
            self.driver.close()

    def run_query(
        self, query: str, parameters: dict = None, database: str = "neo4j"
    ) -> List[Dict[str, Any]]:
        """Cypher 쿼리 실행. 결과를 dict 리스트로 반환."""
        if not self.driver:
            logger.error("[Neo4j] Driver not initialized")
            return []

        try:
            with self.driver.session(database=database) as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as e:
            logger.error(f"[Neo4j] Query error: {e}")
            return []

    def run_write(
        self, query: str, parameters: dict = None, database: str = "neo4j"
    ) -> None:
        """쓰기 전용 Cypher 쿼리 실행."""
        if not self.driver:
            logger.error("[Neo4j] Driver not initialized")
            return

        try:
            with self.driver.session(database=database) as session:
                session.execute_write(lambda tx: tx.run(query, parameters or {}))
        except Exception as e:
            logger.error(f"[Neo4j] Write error: {e}")

    def run_batch(
        self, query: str, batch_params: List[dict], database: str = "neo4j"
    ) -> int:
        """배치 쓰기. UNWIND 패턴으로 대량 INSERT."""
        if not self.driver:
            return 0

        try:
            with self.driver.session(database=database) as session:
                result = session.execute_write(
                    lambda tx: tx.run(query, {"batch": batch_params})
                )
                return len(batch_params)
        except Exception as e:
            logger.error(f"[Neo4j] Batch write error: {e}")
            return 0

    @property
    def is_connected(self) -> bool:
        if not self.driver:
            return False
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False


# Singleton instance
graph_client = Neo4jClient()
