# Alpha-K Refactoring Log: Neo4j & TimescaleDB Integration

**Date:** 2026-02-13
**Author:** Antigravity Agent

## Summary

Refactored the Alpha-K agent pipeline to integrate Neo4j (Graph Database) and prioritize TimescaleDB (Time-series Database) for historical data, reducing reliance on real-time API calls.

## Key Changes

### 1. Infrastructure Layer

- **New `GraphService` (`src/infrastructure/graph/graph_service.py`):**
  - Encapsulates Neo4j queries for Themes, Competitors, Supply Chains, and Group Structure.
  - Improves code maintainability by separating Cypher queries from agent logic.
- **Updated `MarketDataProvider` (`src/infrastructure/data_providers/market_data.py`):**
  - **Primary Source:** TimescaleDB (OHLCV, Investor Trading, Sector Indices).
  - **Secondary Source:** KIS API / FDR (Fallback if data is missing).
  - Reduced API rate limit risks and improved data consistency.

### 2. Agent Layer Refactoring

- **`SectorAgent` (Phase 2):**
  - Now uses Neo4j themes to expand candidate list beyond traditional sectors.
  - Analyze theme momentum using TimescaleDB batch queries.
- **`SmartMoneyAgent` (Phase 3C):**
  - Queries TimescaleDB `investor_trading` table for historical flow analysis.
  - Added **Group Alignment** check using Neo4j (if multiple affiliates show similar buying patterns).
- **`TechnicalAgent` (Phase 3A):**
  - Auto-fetches OHLCV from TimescaleDB if `df` is not provided.
- **`FundamentalAgent` (Phase 3B):**
  - Uses Neo4j to identify peer/competitor groups for relative valuation (PER comparison).
- **`RiskAgent` (Phase 5):**
  - Added **Supply Chain Risk** check using Neo4j (warnings if major suppliers/customers have dropped significantly).

### 3. Supervisor Logic (`src/supervisor/graph.py`)

- Simplified data passing in `deep_dive_node`.
- Agents now handle data loading more autonomously via the refactored `MarketDataProvider`.

## How to Run

1. Ensure Neo4j and TimescaleDB containers are running.
2. Rebuild the Alpha-K container to install new dependencies (`neo4j` driver, `psycopg2`).
   ```bash
   docker-compose up --build alpha-k
   ```
3. Run the verification script (requires local env vars or inside container):
   ```bash
   python services/alpha-k/tests/test_refactoring.py
   ```
