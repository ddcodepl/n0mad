---
page_id: 2450fc11-d335-80bb-8b8e-c8757fe833c8
title: Processing tasks
ticket_id: NOMAD-14
stage: refined
generated_at: 2025-08-04 07:48:31
---

# NOMAD-14 Processing tasks

## Overview
Enhance the task-processing script to automatically transition queued tasks through execution via Claude, update status lifecycle, and provide real-time feedback. This automation reduces manual intervention and improves visibility into task progress.

## Acceptance Criteria
- [ ] **AC1:** When any tickets have status “Queued to run,” the script sets their status to “In progress” before execution.
- [ ] **AC2:** The script invokes Claude (skipping permission checks), executes the prompt `“Process all tasks from the task master, don’t stop unless you finish all of the tasks, after that close the app”`, and upon completion sets the ticket status to “Done.”
- [ ] **AC3:** For each processing step (refining, execution, closing), the script updates the ticket’s `Feedback` property with a timestamped message.

## Technical Requirements

### Core Functionality
- Enumerate tickets via internal Tickets API filtered by `status = "Queued to run"`.
- Update each ticket’s status to `In progress` via `PATCH /tickets/{id}`.
- Invoke Claude engine:
  - Endpoint: `POST /claude/run`
  - Payload:
    ```json
    {
      "skipPermissions": true,
      "prompt": "Process all tasks from the task master, don’t stop unless you finish all of the tasks, after that close the app"
    }
    ```
- On success, update ticket status to `Done`.
- If multiple queued tasks:
  - Read first ticket’s `id` property.
  - Locate task file at `tasks/tasks/<id>.json`.
  - Copy its contents to `<parent_directory>/.ticketmaster/tasks/tasks.json`.
- At each stage, `PATCH /tickets/{id}` with:
  ```json
  {
    "properties": {
      "Feedback": "<ISO timestamp> - <stage description>"
    }
  }
  ```

### Integration Points
- Internal Tickets API (v2.1; OAuth2 bearer token required)
- Claude service API (v1; skipPermissions flag)
- File system access under `<repo_root>/tasks/tasks` and `<repo_root>/.ticketmaster/tasks`
- Node.js fs-extra module for file operations

### Data Requirements
- Database schema change: none
- Ticket object properties:
  - `status` enum update (Queued to run → In progress → Done)
  - `Feedback` string field for step logs
- No bulk data migration required

## Implementation Approach

### Architecture & Design
- Script as standalone Node.js module executed by CI or cron.
- Command pattern:  
  1. fetchQueuedTasks()  
  2. processTask(task)  
     - updateStatus(“In progress”)  
     - copyTaskFileIfNeeded()  
     - invokeClaude()  
     - updateFeedback(“refining”), updateFeedback(“executing”), updateFeedback(“closing”)  
     - updateStatus(“Done”)
- Error handling with retries (up to 3 attempts per API call)
- Logging to console and optional audit log file

### Technology Stack
- Node.js 18.x
- npm packages: `axios@1.4`, `fs-extra@11`, `dotenv@16`
- Justification: existing codebase uses Node.js; axios for HTTP; fs-extra for robust file operations

## Performance & Scalability
- Expected load: <10 tasks/hour; negligible CPU/memory
- Scalability: batch size configurable via env var (`MAX_CONCURRENT=1`)
- Resource utilization: minimal
- No caching required

## Security Considerations
- Claude invocation uses `skipPermissions`; ensure environment is secured
- Store API tokens in encrypted secrets (e.g., AWS Secrets Manager, Vault)
- Sanitize file paths to prevent directory traversal
- Audit logs for all status transitions

## Complexity Estimate
**Medium** - Involves API orchestration, file I/O, multi-step updates, and error-handling logic.

## Additional Notes
- Depends on CLAUDE-API-ACCESS ticket for service credentials
- Risk: potential infinite loop if Claude never returns; mitigation: enforce overall timeout (e.g., 30 minutes)
- Future: parallel task processing, GUI progress dashboard