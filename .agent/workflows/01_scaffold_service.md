---
description: Scaffold a new service following Modular/DDD structure
---

# Scaffold New Service (Modular DDD)

This workflow guides you through creating a new service using **Modular Architecture** (Package by Feature).

## 1. Create Directory Structure

Replace `SERVICE_NAME` (e.g., `services/core-gateway`) and `PRIMARY_DOMAIN` (e.g., `user`).

### For Go:

```bash
# Core structure
mkdir -p services/SERVICE_NAME/cmd/server
mkdir -p services/SERVICE_NAME/config
mkdir -p services/SERVICE_NAME/internal/shared

# Primary Domain (e.g., internal/auth)
mkdir -p services/SERVICE_NAME/internal/PRIMARY_DOMAIN
# Within domain: entity, repository, service, handler are files, not folders usually, but if large:
# mkdir -p services/SERVICE_NAME/internal/PRIMARY_DOMAIN/service
```

### For Python:

```bash
mkdir -p services/SERVICE_NAME/src/modules/PRIMARY_DOMAIN
mkdir -p services/SERVICE_NAME/src/shared
```

## 2. Initialize Dependency Management

```bash
cd services/SERVICE_NAME
# Go
go mod init github.com/nookcoder/woorung-gaksi/services/SERVICE_NAME
# Python
# uv init
```

## 3. Create Base Files

Create a `README.md` describing the service responsibilities.

```bash
echo "# SERVICE_NAME" > services/SERVICE_NAME/README.md
```

## 4. Define Initial Domain

Ask the user for the "Primary Domain" (e.g., Auth, Job).
Create the initial files in `internal/DOMAIN/` (Go) or `src/modules/DOMAIN/` (Python).

- `model.go` / `models.py` (Entity)
- `repository.go` / `repository.py` (Interface)
- `service_test.go` (TDD Start)
