---
page_id: 2450fc11-d335-8011-95f1-ce93769118b6
title: Add option when script all the times listens in the 1 minut periods if there any tasks to process
ticket_id: NOMAD-20
stage: refined
generated_at: 2025-08-04 10:46:54
---

# NOMAD-20 Add continuous polling for queued tasks every minute

## Overview
Introduce a configuration-driven option to enable the application to continuously poll for tasks in the “Queued” status at one-minute intervals and automatically process them. This ensures timely handling of new work without manual trigger.

## Acceptance Criteria
- [ ] **AC1:** Codebase Recon completed; relevant modules/files/services, integration points, and impacted dependencies identified and documented.
- [ ] **AC2:** Continuous polling behavior implemented and verified within existing architecture with regression-safe tests.
- [ ] **AC3:** Polling overhead measured and documented, ensuring average CPU and memory impact remains below agreed thresholds (e.g., <5% CPU, <100 MB RAM).

## Technical Requirements

### Core Functionality
- **Codebase Recon:** Analyze the existing codebase to identify the current task scheduler or polling mechanism, configuration files, task repository interfaces, and processing pipeline modules.
- Define a new configuration parameter (e.g., `enableContinuousPolling: boolean`, `pollingIntervalMinutes: integer`) in the existing settings store.
- Extend or refactor the scheduler/poller component to:
  - Check every `pollingIntervalMinutes` for tasks with status = `Queued`.
  - Fetch the list of queued tasks via the existing TaskRepository or data access layer.
  - Hand off each task to the current processing pipeline or TaskProcessor.
- Ensure idempotency and safe concurrency by locking or marking tasks as “In-Progress” before processing.
- Define input/output contracts:
  - Input: none (poller-driven).
  - Output: invocation of existing task processing API per task object.
- Establish validation rules for the new config (e.g., interval ≥1).

### Integration Points
- Modify the configuration management module to include polling flags and interval.
- Update or extend the scheduler/poller component or service entrypoint.
- Interface with the TaskRepository (or equivalent) to query by status.
- Leverage the existing TaskProcessor (or equivalent) for business logic execution.
- No new external services; reuse existing internal services and interfaces.

### Data Requirements
- No changes to persistent schema; ensure the Task status enumeration includes `Queued` and `In-Progress`.
- No data migration required.
- Validate that tasks returned from the repository conform to the expected model before processing.

## Implementation Approach

### Architecture & Design
- Reuse the existing scheduler component; introduce a configuration toggle to switch between ad-hoc/manual and continuous polling modes.
- Apply the Observer or Strategy pattern to encapsulate polling behavior, allowing future modes (e.g., event-driven).
- Poller flow:
  1. Read config: if `enableContinuousPolling` is `true`.
  2. Schedule a recurring job at `pollingIntervalMinutes`.
  3. Query TaskRepository for `Queued` tasks.
  4. Mark tasks as `In-Progress` and invoke TaskProcessor.
  5. Log summary metrics and errors for each run.

## Performance & Scalability
- Target a maximum of one DB query per minute; expected negligible load under normal task volumes.
- For high throughput, allow tuning of `pollingIntervalMinutes` and consider batching repository calls (e.g., page size).
- Monitor CPU and memory; document baseline before/after enabling.
- No additional caching by default; revisit if query latency increases.

## Security Considerations
- The polling job runs under the existing service identity; no new credentials needed.
- Ensure that task marking and processing respects authorization boundaries.
- Handle exceptions to prevent orphaned locks or tasks remaining in limbo.
- No PII handled by the poller; standard data-protection policies apply.

## Complexity Estimate
**Medium** – Involves configuration extension, scheduler refactoring, safe concurrency handling, and comprehensive testing.

## Additional Notes
- Information Needed:
  - Location and format of the existing configuration files or settings module.
  - Identification of the current scheduler or entrypoint for background jobs.
  - Interfaces and method signatures of TaskRepository and TaskProcessor.
  - Existing test coverage for the polling/scheduling components.
- Dependencies:
  - Coordination with any in-flight changes to task processing logic.
- Risks & Mitigations:
  - Risk: Polling interval too short may overload DB; mitigate by enforcing a minimum interval.
  - Risk: Unhandled errors could halt the polling loop; mitigate via robust error handling and alerting.
- Future Enhancements:
  - Expose runtime control of polling via an administrative API.
  - Support dynamic adjustment of polling intervals based on load or SLA.