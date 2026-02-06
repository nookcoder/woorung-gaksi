# Woorung-Gaksi Project Rules

This document outlines the architectural and development rules for the **Woorung-Gaksi** project.
All agents (AGY) and developers must adhere to these guidelines to ensure consistency, maintainability, and performance.

## 1. Architecture Overview

The system runs on a **Mac Mini M4** using Kubernetes (K8s) or Docker Compose. It follows a Microservices architecture behind a unified Gateway.

### Components

- **Public Ingress**:
  - Clients connect via **Cloudflare Tunnel**.
  - **Gateway (Kong/Nginx)** routes traffic.
- **Services**:
  - **Auth Service (FastAPI)**: Guard layer (Auth, Rate Limiting).
  - **Core API Server**: Handles fast business logic.
  - **Next.js Blog**: Content delivery.
- **Async Workers (The "Brain" & "Workers")**:
  - **Redis Task Queue**: Buffers heavy tasks.
  - **Dev Agent**: Coding tasks.
  - **Media Agent**: Video processing/generation.
  - **Research Agent**: Data scraping/research.
  - **Billing Worker**: Stripe synchronization.
- **Infrastructure**:
  - **PostgreSQL**: Primary data store.
  - **Local Storage/S3**: Large artifact storage (videos).

## 2. Domain-Driven Design (DDD)

We adhere to strict DDD principles to manage complexity.

### Layers

1.  **Domain Layer** (`domain/`):
    - **Pure logic**. NO framework dependencies (no FastAPI, no SQL Alchemy imports).
    - Entities, Value Objects, Domain Events, Repository Interfaces.
    - _Rule_: Changes here are rare and momentous.
2.  **Application Layer** (`application/`):
    - **Use Cases** / Command Handlers.
    - Orchestrates domain objects.
    - _Rule_: Implements the specific business scenarios.
3.  **Infrastructure Layer** (`infrastructure/`):
    - **Adapters**.
    - Database implementations (Repositories), API Clients (Stripe, DeepSeek), Framework controllers (FastAPI routers).
    - _Rule_: Plugs into the Application/Domain layers.

### Directory Structure Example

```
src/
  ├── domain/         # Interfaces, Entities, Value Objects
  ├── application/    # Use Cases, DTOs
  ├── infrastructure/ # DB Adapters, External APIs, Web Framework
  └── main.py         # Entry point (Composition Root)
```

## 3. TDDD & Kent Beck Style

We follow **Test-Driven Design/Development** with a focus on simplicity and confidence.

### The Cycle

1.  **Red**: Write a failing test for the behaviors (Use Case).
    - _Kent Beck_: "Test the behavior, not the implementation."
2.  **Green**: Write the _minimal_ code to pass the test.
    - Do not over-engineer. Hardcode if necessary to pass initially.
3.  **Refactor**: Clean up constraints, remove duplication, improve structure (DDD).
    - "Make it work, Make it right, Make it fast."

### Rules

- **No Code Without Tests**: Every functional change requires a test case.
- **Small Steps**: Commit often (or conceptually move in small increments).
- **Mock External Dependencies**: Use dependency injection (DI) to mock DBs and APIs during unit testing.

## 4. Hardware Efficiency (Mac Mini M4)

We maximize the specific hardware constraints of the Mac Mini M4.

### Strategies

- **Resources**:
  - Define strict CPU/Memory `limits` and `requests` in K8s/Docker to prevent OOM kills impacting the Core API.
  - **Core API**: High priority, low latency.
  - **Agents**: Lower priority, can be throttled.
- **Storage**:
  - Use local NVMe speed for temp processing (Media Agent).
  - Offload cold data to S3 to save local disk space.
- **Concurrency**:
  - Leverage M4's parallelism for the Agents.
  - Use **AsyncIO** everywhere in Python services to handle blocking I/O (DB, Network) without blocking threads.

## 5. Agent Instructions (for AGY)

- When asked to implementing a feature, **ALWAYS** start by defining the **Domain Interface** and a **Test**.
- Do not modify the `domain` layer casually.
- Review `infrastructure` code to ensure it effectively implements `domain` interfaces.
