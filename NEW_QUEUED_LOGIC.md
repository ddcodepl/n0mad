# New Simple Queued Task Processing Logic

## Overview

This document describes the new simplified logic for processing queued tasks in the Nomad application.

## New Command

```bash
uv run main.py --simple-queued
```

## Workflow

The new logic implements exactly what was requested:

### 1. Check for Queued Records
- Query Notion for records with status "Queued to run"
- Get the first available record

### 2. Extract Task ID
- Extract the ticket ID from the record
- Validate that the ID exists

### 3. Locate Task File
- Look for `TASK_DIR/tasks/<TASK_ID>.json` file
- If file doesn't exist, mark task as "Failed" with appropriate description

### 4. Copy Task File
- Replace `~/.taskmaster/tasks/tasks.json` with the found task file
- Create backup of existing tasks.json file
- Validate the copied file is valid JSON

### 5. Update Status to In Progress
- Atomically update the Notion record status to "In progress"
- Ensure only 1 task can be in progress at any time

### 6. Execute Claude Code
- Run Claude Code with the predefined prompt:
  ```
  "Process all tasks from the task master, don't stop unless you finish all of the tasks, after that close the app."
  ```
- Execute without any questions/interruptions
- Timeout after 1 hour if needed

### 7. Update Final Status
- If Claude Code succeeds (exit code 0): Update status to "Done"
- If Claude Code fails: Update status to "Failed" with error description

## Key Features

### Max 1 Task In Progress
- System enforces that only 1 task can be "In progress" at any time
- Before processing a new task, it checks for existing in-progress tasks
- Skips processing if another task is already running

### Error Handling
- Comprehensive error handling at each step
- Failed tasks are marked with appropriate error messages
- Status transitions are validated and atomic

### File Safety
- Creates backups before overwriting taskmaster files
- Validates JSON integrity after file operations
- Proper cleanup and error recovery

### Logging
- Comprehensive logging at each step
- Clear status messages and progress tracking
- Error details for troubleshooting

## File Structure

```
project/
├── src/
│   ├── simple_queued_processor.py  # New processor implementation
│   ├── main.py                     # Updated with --simple-queued mode
│   └── tasks/
│       └── tasks/
│           ├── NOMAD-14.json      # Task files
│           ├── NOMAD-19.json
│           └── NOMAD-20.json
├── .taskmaster/
│   └── tasks/
│       ├── tasks.json             # Target file for Claude Code
│       └── backups/               # Automatic backups
└── test_simple_queued.py          # Test validation script
```

## Usage Examples

### Basic Usage
```bash
# Run the new simple queued processor
uv run main.py --simple-queued
```

### Direct Usage
```bash
# Run the processor directly
python src/simple_queued_processor.py
```

### With Custom Project Root
```bash
python src/simple_queued_processor.py --project-root /path/to/project
```

### Testing
```bash
# Validate the setup
python test_simple_queued.py
```

## Differences from Old Logic

| Aspect | Old Logic | New Logic |
|--------|-----------|-----------|
| Complexity | Complex multi-component system | Simple, direct approach |
| Task Processing | Complex orchestration with multiple managers | Direct file copy + Claude execution |
| Concurrency | Complex multi-queue processing | Simple: max 1 task at a time |
| Error Handling | Distributed across multiple components | Centralized in single processor |
| File Management | Complex backup and restore logic | Simple copy with backup |
| Claude Integration | Complex invocation system | Direct subprocess call |

## Error Scenarios

1. **No Queued Tasks**: Logs info message and exits successfully
2. **Missing Task ID**: Marks task as failed with "Missing ticket ID"
3. **Task File Not Found**: Marks task as failed with "Task file not found"
4. **File Copy Failed**: Marks task as failed with copy error details
5. **Claude Execution Failed**: Marks task as failed with execution error
6. **Status Update Failed**: Logs error but continues processing
7. **Another Task In Progress**: Skips processing and exits

## Testing

The system includes comprehensive testing via `test_simple_queued.py`:
- Directory structure validation
- JSON file format validation
- Module import validation
- Usage examples and documentation

## Migration from Old System

The old `--queued` mode is still available for backward compatibility. The new `--simple-queued` mode provides the requested simplified logic.

To migrate:
1. Test with `--simple-queued` mode
2. Validate results match expectations
3. Update automation to use the new mode
4. Old mode can be deprecated once new mode is validated

## Security Considerations

- File path validation prevents directory traversal attacks
- Atomic status updates prevent race conditions
- Backup creation ensures data safety
- Input validation on all user-provided data
- Proper error handling prevents information leakage