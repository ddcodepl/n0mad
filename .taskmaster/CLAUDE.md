# Task Master AI - Agent Integration Guide

## Essential Commands

### Core Workflow Commands

```bash
# Project Setup
taskmaster init                                    # Initialize Task Master in current project
taskmaster parse-prd .taskmaster/docs/prd.txt      # Generate tasks from PRD document
taskmaster models --setup                        # Configure AI models interactively

# Daily Development Workflow
taskmaster list                                   # Show all tasks with status
taskmaster next                                   # Get next available task to work on
taskmaster show <id>                             # View detailed task information (e.g., taskmaster show 1.2)
taskmaster set-status --id=<id> --status=done    # Mark task complete

# Task Management
taskmaster add-task --prompt="description" --research        # Add new task with AI assistance
taskmaster expand --id=<id> --research --force              # Break task into subtasks
taskmaster update-task --id=<id> --prompt="changes"         # Update specific task
taskmaster update --from=<id> --prompt="changes"            # Update multiple tasks from ID onwards
taskmaster update-subtask --id=<id> --prompt="notes"        # Add implementation notes to subtask

# Analysis & Planning
taskmaster analyze-complexity --research          # Analyze task complexity
taskmaster complexity-report                      # View complexity analysis
taskmaster expand --all --research               # Expand all eligible tasks

# Dependencies & Organization
taskmaster add-dependency --id=<id> --depends-on=<id>       # Add task dependency
taskmaster move --from=<id> --to=<id>                       # Reorganize task hierarchy
taskmaster validate-dependencies                            # Check for dependency issues
taskmaster generate                                         # Update task markdown files (usually auto-called)
```

## Key Files & Project Structure

### Core Files

- `.taskmaster/tasks/tasks.json` - Main task data file (auto-managed)
- `.taskmaster/config.json` - AI model configuration (use `taskmaster models` to modify)
- `.taskmaster/docs/prd.txt` - Product Requirements Document for parsing
- `.taskmaster/tasks/*.txt` - Individual task files (auto-generated from tasks.json)
- `.env` - API keys for CLI usage

### Claude Code Integration Files

- `CLAUDE.md` - Auto-loaded context for Claude Code (this file)
- `.claude/settings.json` - Claude Code tool allowlist and preferences
- `.claude/commands/` - Custom slash commands for repeated workflows
- `.mcp.json` - MCP server configuration (project-specific)

### Directory Structure

```
project/
├── .taskmaster/
│   ├── tasks/              # Task files directory
│   │   ├── tasks.json      # Main task database
│   │   ├── task-1.md      # Individual task files
│   │   └── task-2.md
│   ├── docs/              # Documentation directory
│   │   ├── prd.txt        # Product requirements
│   ├── reports/           # Analysis reports directory
│   │   └── task-complexity-report.json
│   ├── templates/         # Template files
│   │   └── example_prd.txt  # Example PRD template
│   └── config.json        # AI models & settings
├── .claude/
│   ├── settings.json      # Claude Code configuration
│   └── commands/         # Custom slash commands
├── .env                  # API keys
├── .mcp.json            # MCP configuration
└── CLAUDE.md            # This file - auto-loaded by Claude Code
```

## MCP Integration

Task Master provides an MCP server that Claude Code can connect to. Configure in `.mcp.json`:

```json
{
  "mcpServers": {
    "taskmaster-ai": {
      "command": "npx",
      "args": ["-y", "--package=taskmaster-ai", "taskmaster-ai"],
      "env": {
        "ANTHROPIC_API_KEY": "your_key_here",
        "PERPLEXITY_API_KEY": "your_key_here",
        "OPENAI_API_KEY": "OPENAI_API_KEY_HERE",
        "GOOGLE_API_KEY": "GOOGLE_API_KEY_HERE",
        "XAI_API_KEY": "XAI_API_KEY_HERE",
        "OPENROUTER_API_KEY": "OPENROUTER_API_KEY_HERE",
        "MISTRAL_API_KEY": "MISTRAL_API_KEY_HERE",
        "AZURE_OPENAI_API_KEY": "AZURE_OPENAI_API_KEY_HERE",
        "OLLAMA_API_KEY": "OLLAMA_API_KEY_HERE"
      }
    }
  }
}
```

### Essential MCP Tools

```javascript
help; // = shows available taskmaster commands
// Project setup
initialize_project; // = taskmaster init
parse_prd; // = taskmaster parse-prd

// Daily workflow
get_tasks; // = taskmaster list
next_task; // = taskmaster next
get_task; // = taskmaster show <id>
set_task_status; // = taskmaster set-status

// Task management
add_task; // = taskmaster add-task
expand_task; // = taskmaster expand
update_task; // = taskmaster update-task
update_subtask; // = taskmaster update-subtask
update; // = taskmaster update

// Analysis
analyze_project_complexity; // = taskmaster analyze-complexity
complexity_report; // = taskmaster complexity-report
```

## Claude Code Workflow Integration

### Standard Development Workflow

#### 1. Project Initialization

```bash
# Initialize Task Master
taskmaster init

# Create or obtain PRD, then parse it
taskmaster parse-prd .taskmaster/docs/prd.txt

# Analyze complexity and expand tasks
taskmaster analyze-complexity --research
taskmaster expand --all --research
```

If tasks already exist, another PRD can be parsed (with new information only!) using parse-prd with --append flag. This will add the generated tasks to the existing list of tasks..

#### 2. Daily Development Loop

```bash
# Start each session
taskmaster next                           # Find next available task
taskmaster show <id>                     # Review task details

# During implementation, check in code context into the tasks and subtasks
taskmaster update-subtask --id=<id> --prompt="implementation notes..."

# Complete tasks
taskmaster set-status --id=<id> --status=done
```

#### 3. Multi-Claude Workflows

For complex projects, use multiple Claude Code sessions:

```bash
# Terminal 1: Main implementation
cd project && claude

# Terminal 2: Testing and validation
cd project-test-worktree && claude

# Terminal 3: Documentation updates
cd project-docs-worktree && claude
```

### Custom Slash Commands

Create `.claude/commands/taskmaster-next.md`:

```markdown
Find the next available Task Master task and show its details.

Steps:

1. Run `taskmaster next` to get the next task
2. If a task is available, run `taskmaster show <id>` for full details
3. Provide a summary of what needs to be implemented
4. Suggest the first implementation step
```

Create `.claude/commands/taskmaster-complete.md`:

```markdown
Complete a Task Master task: $ARGUMENTS

Steps:

1. Review the current task with `taskmaster show $ARGUMENTS`
2. Verify all implementation is complete
3. Run any tests related to this task
4. Mark as complete: `taskmaster set-status --id=$ARGUMENTS --status=done`
5. Show the next available task with `taskmaster next`
```

## Tool Allowlist Recommendations

Add to `.claude/settings.json`:

```json
{
  "allowedTools": [
    "Edit",
    "Bash(taskmaster *)",
    "Bash(git commit:*)",
    "Bash(git add:*)",
    "Bash(npm run *)",
    "mcp__task_master_ai__*"
  ]
}
```

## Configuration & Setup

### API Keys Required

At least **one** of these API keys must be configured:

- `ANTHROPIC_API_KEY` (Claude models) - **Recommended**
- `PERPLEXITY_API_KEY` (Research features) - **Highly recommended**
- `OPENAI_API_KEY` (GPT models)
- `GOOGLE_API_KEY` (Gemini models)
- `MISTRAL_API_KEY` (Mistral models)
- `OPENROUTER_API_KEY` (Multiple models)
- `XAI_API_KEY` (Grok models)

An API key is required for any provider used across any of the 3 roles defined in the `models` command.

### Model Configuration

```bash
# Interactive setup (recommended)
taskmaster models --setup

# Set specific models
taskmaster models --set-main claude-3-5-sonnet-20241022
taskmaster models --set-research perplexity-llama-3.1-sonar-large-128k-online
taskmaster models --set-fallback gpt-4o-mini
```

## Task Structure & IDs

### Task ID Format

- Main tasks: `1`, `2`, `3`, etc.
- Subtasks: `1.1`, `1.2`, `2.1`, etc.
- Sub-subtasks: `1.1.1`, `1.1.2`, etc.

### Task Status Values

- `pending` - Ready to work on
- `in-progress` - Currently being worked on
- `done` - Completed and verified
- `deferred` - Postponed
- `cancelled` - No longer needed
- `blocked` - Waiting on external factors

### Task Fields

```json
{
  "id": "1.2",
  "title": "Implement user authentication",
  "description": "Set up JWT-based auth system",
  "status": "pending",
  "priority": "high",
  "dependencies": ["1.1"],
  "details": "Use bcrypt for hashing, JWT for tokens...",
  "testStrategy": "Unit tests for auth functions, integration tests for login flow",
  "subtasks": []
}
```

## Claude Code Best Practices with Task Master

### Context Management

- Use `/clear` between different tasks to maintain focus
- This CLAUDE.md file is automatically loaded for context
- Use `taskmaster show <id>` to pull specific task context when needed

### Iterative Implementation

1. `taskmaster show <subtask-id>` - Understand requirements
2. Explore codebase and plan implementation
3. `taskmaster update-subtask --id=<id> --prompt="detailed plan"` - Log plan
4. `taskmaster set-status --id=<id> --status=in-progress` - Start work
5. Implement code following logged plan
6. `taskmaster update-subtask --id=<id> --prompt="what worked/didn't work"` - Log progress
7. `taskmaster set-status --id=<id> --status=done` - Complete task

### Complex Workflows with Checklists

For large migrations or multi-step processes:

1. Create a markdown PRD file describing the new changes: `touch task-migration-checklist.md` (prds can be .txt or .md)
2. Use Taskmaster to parse the new prd with `taskmaster parse-prd --append` (also available in MCP)
3. Use Taskmaster to expand the newly generated tasks into subtasks. Consdier using `analyze-complexity` with the correct --to and --from IDs (the new ids) to identify the ideal subtask amounts for each task. Then expand them.
4. Work through items systematically, checking them off as completed
5. Use `taskmaster update-subtask` to log progress on each task/subtask and/or updating/researching them before/during implementation if getting stuck

### Git Integration

Task Master works well with `gh` CLI:

```bash
# Create PR for completed task
gh pr create --title "Complete task 1.2: User authentication" --body "Implements JWT auth system as specified in task 1.2"

# Reference task in commits
git commit -m "feat: implement JWT auth (task 1.2)"
```

### Parallel Development with Git Worktrees

```bash
# Create worktrees for parallel task development
git worktree add ../project-auth feature/auth-system
git worktree add ../project-api feature/api-refactor

# Run Claude Code in each worktree
cd ../project-auth && claude    # Terminal 1: Auth work
cd ../project-api && claude     # Terminal 2: API work
```

## Troubleshooting

### AI Commands Failing

```bash
# Check API keys are configured
cat .env                           # For CLI usage

# Verify model configuration
taskmaster models

# Test with different model
taskmaster models --set-fallback gpt-4o-mini
```

### MCP Connection Issues

- Check `.mcp.json` configuration
- Verify Node.js installation
- Use `--mcp-debug` flag when starting Claude Code
- Use CLI as fallback if MCP unavailable

### Task File Sync Issues

```bash
# Regenerate task files from tasks.json
taskmaster generate

# Fix dependency issues
taskmaster fix-dependencies
```

DO NOT RE-INITIALIZE. That will not do anything beyond re-adding the same Taskmaster core files.

## Important Notes

### AI-Powered Operations

These commands make AI calls and may take up to a minute:

- `parse_prd` / `taskmaster parse-prd`
- `analyze_project_complexity` / `taskmaster analyze-complexity`
- `expand_task` / `taskmaster expand`
- `expand_all` / `taskmaster expand --all`
- `add_task` / `taskmaster add-task`
- `update` / `taskmaster update`
- `update_task` / `taskmaster update-task`
- `update_subtask` / `taskmaster update-subtask`

### File Management

- Never manually edit `tasks.json` - use commands instead
- Never manually edit `.taskmaster/config.json` - use `taskmaster models`
- Task markdown files in `tasks/` are auto-generated
- Run `taskmaster generate` after manual changes to tasks.json

### Claude Code Session Management

- Use `/clear` frequently to maintain focused context
- Create custom slash commands for repeated Task Master workflows
- Configure tool allowlist to streamline permissions
- Use headless mode for automation: `claude -p "taskmaster next"`

### Multi-Task Updates

- Use `update --from=<id>` to update multiple future tasks
- Use `update-task --id=<id>` for single task updates
- Use `update-subtask --id=<id>` for implementation logging

### Research Mode

- Add `--research` flag for research-based AI enhancement
- Requires a research model API key like Perplexity (`PERPLEXITY_API_KEY`) in environment
- Provides more informed task creation and updates
- Recommended for complex technical tasks

---

_This guide ensures Claude Code has immediate access to Task Master's essential functionality for agentic development workflows._
