---
page_id: 2450fc11-d335-8062-8f13-d680e1466619
title: Organize code
ticket_id: NOMAD-9
stage: refined
generated_at: 2025-08-04 07:48:32
---

# NOMAD-9 Codebase Reorganization and Logging Enhancements

## Overview
Reorganize the repository into self-descriptive, modular directories and consolidate entry scripts. Implement a consistent logging strategy that writes per-session logs to `./logs/<timestamp>.log`.

## Acceptance Criteria
- [ ] **AC1:** All client modules reside in `/clients`, others in `/services`, `/workflows`, `/utils`, etc., with clear, self-documenting names.
- [ ] **AC2:** `main.py` and `main_workflow.py` are merged into a single entrypoint (e.g., `main.py`) preserving all existing workflows.
- [ ] **AC3:** Each execution session initializes a logger that writes to `./logs/<YYYYMMDD_HHMMSS>.log` using the timestamp at session start.

## Technical Requirements

### Core Functionality
- Define new directory structure:
  - `/clients` for all API/client integrations
  - `/services` for business logic
  - `/workflows` for orchestration logic
  - `/utils` for shared helpers (e.g., logger factory)
- Merge `main.py` and `main_workflow.py` into one `main.py`, exposing `if __name__ == "__main__": run()`.
- Implement a `LoggerFactory` in `/utils/logger.py`:
  - Creates a root logger with console and file handlers
  - File handler writes to `./logs/{timestamp}.log`
  - Timestamp format: `YYYYMMDD_HHMMSS`
  - Standard log format: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
- Validate directory existence at startup and create `/logs` if missing.

### Integration Points
- No external APIs are changed; code references must be updated to new import paths.
- Use Python’s built-in `logging` module (>=3.7).
- Ensure `requirements.txt` and Dockerfile (if present) reflect any new dependencies or path changes.

### Data Requirements
- No database schema changes required.
- No data migrations required.
- Validate logger file path and write permissions.

## Implementation Approach

### Architecture & Design
- Adopt a package-based layout with explicit `__init__.py` files.
- Use the Single Responsibility pattern: each directory only contains code for one purpose.
- Component interaction:
  1. `main.py` calls initialization in `/utils/logger.py`
  2. Instantiates services/clients/workflows via imports
  3. Executes orchestration logic
  4. Logs all events to console and file

### Technology Stack
- Python 3.9+
- Standard `logging` library
- No new external libraries; reuse existing components where possible
- Update CI/CD pipeline scripts to run the new `main.py`

## Performance & Scalability
- Logging overhead: minimal CPU/memory impact under typical loads.
- Directory validations and logger initialization incur negligible startup cost.
- Future: implement `RotatingFileHandler` if log sizes grow.

## Security Considerations
- Do not log sensitive data (PII, credentials).
- Ensure `./logs` directory permissions restrict unauthorized access.
- Use safe log formatting to avoid injection.

## Complexity Estimate
**Medium** - Involves repository-wide refactoring, import path updates, and a standardized logging mechanism.

## Additional Notes
- Depends on completion of NOMAD-7 (authentication refactor).
- Risk: broken imports and missing modules; mitigate with integration tests.
- Future: introduce configuration management for log levels and destinations.