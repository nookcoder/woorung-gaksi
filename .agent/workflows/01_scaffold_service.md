---
description: Scaffold a new service following DDD structure
---

# Scaffold New Service (DDD)

This workflow guides you through creating a new service (e.g., `auth-service`, `core-api`) with the proper Domain-Driven Design directory structure.

## 1. Create Directory Structure

Ideally, replace `SERVICE_NAME` with the name of your service (e.g., `services/core-api`).

```bash
mkdir -p services/SERVICE_NAME/src/domain/entities
mkdir -p services/SERVICE_NAME/src/domain/repositories
mkdir -p services/SERVICE_NAME/src/domain/events
mkdir -p services/SERVICE_NAME/src/application/use_cases
mkdir -p services/SERVICE_NAME/src/application/dtos
mkdir -p services/SERVICE_NAME/src/infrastructure/db
mkdir -p services/SERVICE_NAME/src/infrastructure/web
mkdir -p services/SERVICE_NAME/src/infrastructure/external
mkdir -p services/SERVICE_NAME/tests/unit
mkdir -p services/SERVICE_NAME/tests/integration
```

## 2. Initialize Dependency Management

Initialize `uv` or `poetry` or `go mod` depending on the language.
(Example for Python/uv)

```bash
cd services/SERVICE_NAME
# uv init or similar
echo "src/" > .sources
```

## 3. Create Base Files

Create a `README.md` describing the service responsibilities.

```bash
echo "# SERVICE_NAME" > services/SERVICE_NAME/README.md
```

## 4. Define Initial Domain

Ask the user for the primary "Aggregate Root" entity (e.g., `User` for Auth, `Job` for Core).
Create the file in `src/domain/entities/`.

## 5. Setup CI/CD Skeleton

Ensure there is a Dockerfile in `services/SERVICE_NAME/Dockerfile` optimized for the requested runtime.
