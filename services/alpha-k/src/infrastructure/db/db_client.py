"""
Database Client for TimescaleDB
================================
Singleton class to manage PostgreSQL connection pool.
"""
import os
import logging
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
from typing import Optional, List, Any

logger = logging.getLogger(__name__)

class DatabaseClient:
    _instance = None
    _pool: Optional[pool.SimpleConnectionPool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseClient, cls).__new__(cls)
            cls._instance._initialize_pool()
        return cls._instance

    def _initialize_pool(self):
        """Initialize connection pool from environment variables."""
        try:
            # DB_URI format: postgresql://user:pass@host:port/dbname
            # Or separate env vars
            db_uri = os.getenv("DB_URI")
            min_conn = 1
            max_conn = 10
            
            if db_uri:
                self._pool = psycopg2.pool.SimpleConnectionPool(min_conn, max_conn, dsn=db_uri)
            else:
                user = os.getenv("POSTGRES_USER", "woorung")
                password = os.getenv("POSTGRES_PASSWORD", "gaksi")
                host = os.getenv("POSTGRES_HOST", "timescaledb")
                port = os.getenv("POSTGRES_PORT", "5432")
                dbname = os.getenv("POSTGRES_DB", "woorung_db")
                
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    min_conn, max_conn,
                    user=user, password=password,
                    host=host, port=port, database=dbname
                )
            logger.info("[DatabaseClient] Connection pool initialized")
            
        except Exception as e:
            logger.error(f"[DatabaseClient] Failed to initialize pool: {e}")
            self._pool = None

    @contextmanager
    def get_cursor(self):
        """Context manager to yield a cursor from a pooled connection."""
        if not self._pool:
            logger.error("[DatabaseClient] Pool not initialized. Re-initializing...")
            self._initialize_pool()
            if not self._pool:
                raise Exception("Database connection failed")

        conn = self._pool.getconn()
        try:
            with conn.cursor() as cursor:
                yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"[DatabaseClient] Transaction failed: {e}")
            raise
        finally:
            self._pool.putconn(conn)

    def execute(self, query: str, params: tuple = None):
        """Execute a single query without return value."""
        with self.get_cursor() as cur:
            cur.execute(query, params)

    def fetch_all(self, query: str, params: tuple = None) -> List[Any]:
        """Execute query and return all rows."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

    def fetch_one(self, query: str, params: tuple = None) -> Any:
        """Execute query and return one row."""
        with self.get_cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()

# Global Instance
db_client = DatabaseClient()
