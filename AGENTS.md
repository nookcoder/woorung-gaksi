# AGENTS.md - Developer Guide for AI Agents

This document defines the protocols, styles, and workflows for AI agents (OpenCode, Manager, etc.) working on Woorung-Gaksi.

**Reference Sources:**
- Context: `.agent/rules/PRODUCT_CONTEXT.md`
- Rules: `.agent/rules/PROJECT_RULES.md`
- Workflows: `.agent/workflows/*.md`

## 1. Project Identity
**Woorung-Gaksi (우렁각시)**: A local-first AI orchestration platform running on Apple Silicon (M4).
- **Goal**: Automate 90% of software/content tasks.
- **Constraint**: Low memory footprint, high concurrency (Go Gateway + Python Agents).

## 2. Directory Structure & Stack

### 🟢 Core Gateway (Go)
**Path**: `services/core-gateway`
- **Role**: API Gateway, Auth, High-perf Orchestration.
- **Stack**: Go 1.24, Gin, Gorm/SQL, JWT.
- **Structure**: Modular DDD (`internal/auth`, `internal/user`).

### 🔵 Python Agents (Python)
**Path**: `services/pm-agent`, `services/dev-agent`
- **Role**: Complex Logic (LLM), Research, Media Processing.
- **Stack**: Python 3.11+, FastAPI, LangGraph, Pydantic.
- **Tooling**: `uv` (Package Manager), `ruff` (Lint), `pytest`.
- **Skills**: Located in `src/tools/`. See `src/tools/README.md`.

## 3. Development Guidelines

### Domain-Driven Design (DDD)
- **Domain Layer**: Pure business logic and interfaces. Zero dependencies.
- **Application Layer**: Use Cases that orchestrate domain objects.
- **Infrastructure Layer**: Implementation details (DB, API, Web).
- **Strategy**: **Package by Feature** (keep related domain/app/infra logic close if possible, or strictly layered).

### Test-Driven Development (TDD)
1.  **Red**: Write a failing test for the Use Case.
2.  **Green**: Write minimal code to pass.
3.  **Refactor**: Clean up and optimize.
*Never skip the test phase.*

### Hardware Optimization (M4)
- **Go**: Use for high-throughput, low-latency tasks.
- **Python**: Use `asyncio` for I/O bound tasks. Offload heavy processing to background workers.

## 4. Commands Reference

| Action | Go (`services/core-gateway`) | Python (`services/pm-agent`) |
| :--- | :--- | :--- |
| **Install** | `go mod download` | `uv sync` |
| **Run** | `go run ./cmd/server/main.go` | `uv run uvicorn src.main:app --reload` |
| **Test** | `go test ./...` | `uv run pytest` |
| **Lint** | `golangci-lint run` | `uv run ruff check .` |

## 5. Agent Workflows

### 🛠 Scaffold New Service
*Ref: `.agent/workflows/01_scaffold_service.md`*
- Creates the folder structure (`internal/domain`, `src/modules`).
- Initializes module/dependency managers.

### ⚡ Implement Feature
*Ref: `.agent/workflows/02_implement_feature_tddd.md`*
- Defines Use Case -> Writes Test -> Implements Domain/Infra.

### 🤖 Orchestrate Job
*Ref: `.agent/workflows/03_orchestrate_agent_job.md`*
- PM Agent breaks down tasks -> Dispatches to Redis -> Workers execute.

## 6. Developing Skills (Tools)

Skills are Python functions that agents can call to perform actions (e.g., search web, write file).

**Location**: `services/pm-agent/src/tools/`

### How to Add a Skill
1.  Create a file in `src/tools/` (e.g., `web_search.py`).
2.  Define the tool using LangChain's `@tool` decorator.
3.  Add rigorous **Type Hints** and **Docstrings**. The LLM relies on these to understand the tool.
4.  Register the tool in the agent's graph (`src/modules/manager/graph.py`).

### Best Practices
- **Atomic**: Each tool should do one thing well.
- **Safe**: Validate inputs using Pydantic.
- **documented**: Explain *when* to use the tool in the docstring.

Example:
```python
@tool
def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two integers. Use this for basic addition."""
    return a + b
```
