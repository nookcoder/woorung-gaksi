import os
import logging
import sys

# Add src module to path if running directly
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.infrastructure.db.db_client import db_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migrations():
    """Run all SQL files in the migrations directory."""
    migration_dir = os.path.join(os.path.dirname(__file__), "migrations")
    if not os.path.exists(migration_dir):
        logger.warning(f"Metadata migration directory not found: {migration_dir}")
        return

    files = sorted([f for f in os.listdir(migration_dir) if f.endswith(".sql")])
    
    for filename in files:
        filepath = os.path.join(migration_dir, filename)
        logger.info(f"[DB] Applying migration: {filename}")
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                sql = f.read()
            
            db_client.execute(sql)
            logger.info(f"[DB] Migration {filename} applied successfully")
            
        except Exception as e:
            logger.error(f"[DB] Failed to apply migration {filename}: {e}")

if __name__ == "__main__":
    run_migrations()
