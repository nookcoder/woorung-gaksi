from contextlib import asynccontextmanager
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import os

# Get DB settings from Env
# Prioritize standard POSTGRES_* vars, fallback to old keys or defaults for safety (though defaults should be avoided)
DB_HOST = os.getenv("POSTGRES_HOST") or os.getenv("DB_Host", "timescaledb")
DB_PORT = os.getenv("POSTGRES_PORT") or os.getenv("DB_Port", "5432")
DB_USER = os.getenv("POSTGRES_USER") or os.getenv("DB_User", "woorung")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_Password", "gaksi")
DB_NAME = os.getenv("POSTGRES_DB") or os.getenv("DB_Name", "woorung_db")

DB_URI = os.getenv("DB_URI")
if not DB_URI:
    DB_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

@asynccontextmanager
async def get_postgres_checkpointer():
    """
    Context manager that yields an initialized AsyncPostgresSaver.
    Manages the connection pool lifecycle.
    """
    # 1. Setup tables using a temporary autocommit connection
    # This is required because CREATE INDEX CONCURRENTLY cannot run in a transaction block
    async with await AsyncConnection.connect(DB_URI, autocommit=True) as conn:
        temp_checkpointer = AsyncPostgresSaver(conn)
        await temp_checkpointer.setup()
    
    # 2. Use connection pool for regular operations
    async with AsyncConnectionPool(DB_URI, min_size=1, max_size=10) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        yield checkpointer
