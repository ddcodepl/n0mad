# Notion Developer - Task Refinement Automation

An automated tool that polls Notion databases for tasks with "To Refine" status, processes them with OpenAI GPT, and updates the tasks with refined content.

## Features

- = Continuous polling of Notion database (60-second intervals)
- > OpenAI GPT-4 integration for content refinement
- =� Automatic saving of refined content to markdown files
- =� Comprehensive logging and error handling
- =� Graceful shutdown support
- =� Performance metrics tracking

## Setup

1. Install dependencies:

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

2. Configure environment variables:

```bash
cp .env.example .env
```

Edit `.env` and add:

- `NOTION_TOKEN`: Your Notion integration token
- `NOTION_BOARD_DB`: Your Notion database ID
- `OPENAI_API_KEY`: Your OpenAI API key

## Usage

Run the application:

```bash
python main.py
```

The application will:

1. Poll your Notion database every 60 seconds
2. Find tasks with "To Refine" status
3. Process content with GPT-4
4. Save refined content to `tasks/` directory
5. Update task status to "Refined"

## Task Status Flow

1. **Ideas** � Initial task concepts
2. **To Refine** � Ready for AI processing (monitored status)
3. **Refined** � Successfully processed
4. **Failed** � Processing error occurred

## Logs

- Console output: Real-time activity
- `nomad.log`: Persistent log file with timestamps

## Graceful Shutdown

Press `Ctrl+C` to stop the application. It will complete any in-progress task and log final statistics.
