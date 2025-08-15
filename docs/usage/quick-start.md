# Quick Start Guide

Get up and running with Nomad in under 10 minutes! This guide walks you through installation, setup, and your first task processing.

## Overview

By the end of this guide, you'll have:
- ✅ Nomad installed and configured
- ✅ API keys set up for Notion and AI providers
- ✅ Processed your first task
- ✅ Understanding of basic commands and workflows

**Time Required**: ~10 minutes
**Prerequisites**: Python 3.8+, internet connection

## Step 1: Installation (2 minutes)

### Quick Installation
The fastest way to get started:

```bash
curl -sSL https://raw.githubusercontent.com/nomad-notion-automation/nomad/main/install.sh | bash
```

### Verify Installation
```bash
nomad --version
```
Expected output: `Nomad v0.2.0 - Notion Automation Tool`

> **Having trouble?** See [Installation Troubleshooting](../installation/troubleshooting-installation.md)

## Step 2: Get Your API Keys (3 minutes)

You'll need API keys from Notion and at least one AI provider.

### Notion API Key (Required)

1. **Create Integration**:
   - Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Name it "Nomad Automation"
   - Select your workspace
   - Click "Submit"

2. **Copy Token**:
   - Copy the "Internal Integration Token" (starts with `secret_`)
   - Keep this safe - you'll need it shortly

3. **Share Database**:
   - Go to your Notion database/board
   - Click "Share" in top-right
   - Invite your integration: type "Nomad Automation"
   - Set permissions to "Can edit"

4. **Get Database ID**:
   - Copy your database URL
   - Extract the ID: `https://notion.so/workspace/DATABASE_ID?v=...`
   - It's the 32-character string after the last `/`

### AI Provider API Key (Choose One)

Pick one AI provider to start with:

#### Option A: OpenAI (Recommended)
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click "Create new secret key"
3. Copy the key (starts with `sk-`)

#### Option B: Anthropic (Claude)
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Navigate to "API Keys"
3. Create new key
4. Copy the key (starts with `sk-ant-`)

#### Option C: OpenRouter (Multi-Model)
1. Go to [openrouter.ai/keys](https://openrouter.ai/keys)
2. Create account and add credits
3. Generate API key
4. Copy the key (starts with `sk-or-`)

## Step 3: Configure Nomad (2 minutes)

### Create Configuration
```bash
nomad --config-create
```

This creates a configuration file at `~/.nomad/config.env`.

### Add Your API Keys
Edit the configuration file:

```bash
# Use your preferred editor
nano ~/.nomad/config.env
# or
code ~/.nomad/config.env
```

Add your API keys:
```env
# Notion Integration (Required)
NOTION_TOKEN=secret_your_notion_token_here
NOTION_BOARD_DB=your_database_id_here

# AI Provider (Choose one or more)
OPENAI_API_KEY=sk-your_openai_key_here
# ANTHROPIC_API_KEY=sk-ant-your_anthropic_key_here
# OPENROUTER_API_KEY=sk-or-your_openrouter_key_here
```

### Activate Configuration
```bash
export NOMAD_CONFIG_FILE=~/.nomad/config.env

# Make it permanent (choose your shell)
echo 'export NOMAD_CONFIG_FILE=~/.nomad/config.env' >> ~/.bashrc
# or for zsh:
echo 'export NOMAD_CONFIG_FILE=~/.nomad/config.env' >> ~/.zshrc
```

### Verify Configuration
```bash
nomad --config-status
```

You should see ✅ for all required variables.

## Step 4: Health Check (1 minute)

Run a comprehensive health check:

```bash
nomad --health-check
```

Expected output:
```
🏥 Nomad Health Check
==================

✅ Python 3.9.7 detected (requirement: 3.8+)
✅ NOTION_TOKEN configured
✅ NOTION_BOARD_DB configured
✅ OPENAI_API_KEY configured and valid
✅ Home: ~/.nomad (readable/writable)
✅ Tasks: ~/.nomad/tasks (readable/writable)

📊 Overall Status:
✅ System is healthy and ready to use!
```

> **Issues?** Check [Configuration Troubleshooting](troubleshooting/configuration.md)

## Step 5: Your First Task Processing (2 minutes)

Now let's process some tasks! You'll need tasks in your Notion database with specific statuses.

### Check Available Tasks
```bash
nomad --help
```

### Process "To Refine" Tasks
If you have tasks with "To Refine" status:

```bash
nomad --refine
```

Expected output:
```
🚀 Starting refine mode - processing tasks with 'To Refine' status...
Found 3 valid tasks to process concurrently
✅ Task TASK-123 processed successfully
✅ Task TASK-124 processed successfully
✅ Task TASK-125 processed successfully
🏁 Completed concurrent processing of 3 tasks
```

### Process "Prepare Tasks" Status
If you have tasks with "Prepare Tasks" status:

```bash
nomad --prepare
```

### Process "Queued to run" Tasks
If you have tasks with "Queued to run" status:

```bash
nomad --queued
```

### Multi-Status Processing
Process multiple status types:

```bash
nomad --multi
```

### Continuous Mode (Background Processing)
Run continuously and check every minute:

```bash
nomad
```

Press `Ctrl+C` to stop.

## What Just Happened?

Nomad just:

1. **Connected to Notion**: Retrieved tasks from your database
2. **Applied AI Processing**: Enhanced task descriptions with AI
3. **Updated Notion**: Saved improved content back to your database
4. **Logged Progress**: Provided detailed feedback on processing

## Essential Commands Reference

Now that you're set up, here are the commands you'll use most:

```bash
# Status and info
nomad --version              # Check version
nomad --config-status        # Check configuration
nomad --health-check         # System health
nomad --help                # Show all commands

# Processing modes
nomad --refine              # Process "To Refine" tasks
nomad --prepare             # Process "Prepare Tasks"
nomad --queued              # Process "Queued to run" tasks
nomad --multi               # Multi-status processing
nomad                       # Continuous polling (default)

# Configuration
nomad --config-create       # Create config template
nomad --config-help         # Configuration help
```

## Next Steps

🎉 **Congratulations!** You now have Nomad running. Here's what to explore next:

### Immediate Next Steps
1. **[Learn Basic Operations](basic-operations.md)** - Master everyday commands
2. **[Understand Processing Modes](processing-modes/)** - Deep dive into different modes
3. **[Set Up Slack Integration](integrations/slack-setup.md)** - Get notifications

### For Regular Usage
1. **[Common Tasks Guide](common-tasks.md)** - Daily usage patterns
2. **[Workflow Automation](workflows/automation.md)** - Automate your processes
3. **[Best Practices](best-practices.md)** - Optimize your setup

### For Teams and Advanced Users
1. **[Team Collaboration](workflows/team-collaboration.md)** - Multi-user setup
2. **[Advanced Configuration](advanced-configuration.md)** - Power user features
3. **[API Integration](api-integration.md)** - Programmatic usage

## Common First-Time Issues

### "No tasks found"
- **Check your Notion database** for tasks with the expected status
- **Verify database sharing** with your integration
- **Check task status names** match exactly (case-sensitive)

### "API key invalid"
- **Double-check API key format** (no extra spaces/characters)
- **Verify permissions** for Notion integration
- **Try regenerating keys** if format looks correct

### "Connection failed"
- **Check internet connection**
- **Verify firewall settings** (allow HTTPS to api.notion.com, api.openai.com, etc.)
- **Try from different network** if behind corporate firewall

### Performance seems slow
- **This is normal for first run** - subsequent runs are faster
- **Check your internet speed** - API calls require good connectivity
- **Consider using GPT-3.5-turbo** instead of GPT-4 for faster processing

## Example Notion Database Setup

If you don't have a Notion database yet, here's a quick setup:

### 1. Create Database
1. In Notion, type `/database` and select "Table - Full page"
2. Name it "Task Management" or similar

### 2. Add Required Properties
Make sure your database has these properties:
- **Name** (Title) - Task titles
- **Status** (Select) - Task status with options:
  - "To Refine"
  - "Prepare Tasks"
  - "Queued to run"
  - "In Progress"
  - "Done"
  - "Failed"

### 3. Add Sample Tasks
Create a few sample tasks:
- Set **Name** to something like "Improve user documentation"
- Set **Status** to "To Refine"
- Add some content in the page body

### 4. Share Database
- Click "Share" → Invite your "Nomad Automation" integration
- Set permissions to "Can edit"

Now you're ready to process tasks!

## Getting Help

**Stuck?** Here's where to get help:

1. **Check the docs**: [Usage Documentation](README.md)
2. **Common issues**: [Troubleshooting Guide](troubleshooting/)
3. **Ask questions**: [GitHub Discussions](https://github.com/nomad-notion-automation/nomad/discussions)
4. **Report bugs**: [GitHub Issues](https://github.com/nomad-notion-automation/nomad/issues)

## What's Next?

You're now ready to dive deeper into Nomad! Here are some recommended paths:

**For Daily Users:**
1. [Basic Operations](basic-operations.md) → [Common Tasks](common-tasks.md) → [Best Practices](best-practices.md)

**For Team Leads:**
1. [Team Setup](configuration-examples/team.md) → [Slack Integration](integrations/slack-setup.md) → [Collaboration Workflow](workflows/team-collaboration.md)

**For Developers:**
1. [API Integration](api-integration.md) → [Custom Processors](custom-processors.md) → [Examples](../examples/)

**For System Administrators:**
1. [Production Setup](configuration-examples/production.md) → [Enterprise Deployment](enterprise-deployment.md) → [Monitoring](integrations/monitoring.md)

---

**🎉 Welcome to the Nomad community!** You're now part of a growing ecosystem of users automating their task management with AI. Happy automating!

---

*Quick Start Guide for Nomad v0.2.0. Need help? Check our [FAQ](faq.md) or [ask the community](https://github.com/nomad-notion-automation/nomad/discussions).*
