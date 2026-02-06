---
description: Implement a feature using TDDD and Kent Beck style
---

# Implement Feature (TDDD)

This workflow enforces the TDD/DDD cycle: "Red -> Green -> Refactor".

## 1. Understand the Goal

1.  Identify the **UseCase** name (e.g., `CreateJob`, `RegisterUser`).
2.  Define the Input (DTO) and Output (Result).

## 2. Step 1: Write a Failing Test (Red)

Create a test file in `tests/unit/use_cases/`.
This test should instantiate the Use Case and mock the dependencies (Repositories).

```python
# Example: tests/unit/use_cases/test_create_job.py
def test_create_job_success():
    # Arrange
    repo = MockJobRepository()
    use_case = CreateJobUseCase(repo)
    command = CreateJobCommand(title="Video Edit")

    # Act
    result = use_case.execute(command)

    # Assert
    assert result.job_id is not None
    assert repo.save_called is True
```

_Status Check_: Run the test. It MUST fail (compilation error or assertion error).

## 3. Step 2: Make It Work (Green)

Write the _minimum_ amount of code to satisfy the test.

1.  Define the `UseCase` class.
2.  Define the `Command` DTO.
3.  Define the `Repository` interface (in `domain`).
4.  Implement the logic in `execute`.

_Status Check_: Run the test. It MUST pass.

## 4. Step 3: Refactor (Refactor)

1.  Check for violations of DDD (is logic leaking into the controller?).
2.  Optimize performance (if necessary).
3.  Ensure hardware is not wasted (e.g., if this triggers a heavy task, ensure it's queued to Redis, not run in-process).

## 5. Integration Test

Once the logic is solid, write an infrastructure test (e.g., with a real DB container).
