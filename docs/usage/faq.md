# Frequently Asked Questions (FAQ)

Quick answers to the most common questions about Nomad. Can't find your answer? Check our [troubleshooting guide](troubleshooting/) or [ask the community](https://github.com/nomad-notion-automation/nomad/discussions).

## Table of Contents
- [Installation and Setup](#installation-and-setup)
- [Configuration](#configuration)  
- [Task Processing](#task-processing)
- [Integrations](#integrations)
- [Performance](#performance)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

---

## Installation and Setup

### Q: What are the system requirements for Nomad?
**A:** Nomad requires:
- **Python**: 3.8 or higher (3.9+ recommended)
- **Operating System**: macOS, Linux, or Windows with WSL
- **Memory**: Minimum 512MB, recommended 1GB+
- **Storage**: ~200MB for installation and basic usage
- **Network**: Internet connectivity for API calls

### Q: Can I install Nomad on Windows?
**A:** Yes! Nomad works on Windows in several ways:
- **WSL2** (recommended): Full compatibility
- **Native Windows**: Basic functionality (some features may be limited)
- **Docker**: Full compatibility in containers

### Q: How do I update Nomad to the latest version?
**A:** Update using pip:
```bash
pip install --upgrade nomad-notion-automation
```

Check your version after updating:
```bash
nomad --version
```

### Q: Can I install Nomad without admin/sudo privileges?
**A:** Yes! Use the user installation method:
```bash
pip install --user nomad-notion-automation
```

You may need to add `~/.local/bin` to your PATH.

### Q: The installation seems to hang or take forever
**A:** This can happen due to:
- **Slow internet**: Package downloads can be large
- **Compiling dependencies**: Some packages need compilation
- **Network restrictions**: Corporate firewalls may block access

Try:
```bash
pip install --upgrade pip
pip install --verbose nomad-notion-automation
```

---

## Configuration

### Q: Where does Nomad store its configuration?
**A:** Nomad uses multiple configuration sources:
- **Global config**: `~/.nomad/config.env` (created with `--config-create`)
- **Local config**: `.env` file in current directory
- **Environment variables**: System environment variables

Priority: Environment variables > Local .env > Global config

### Q: How do I switch between different configurations?
**A:** Use the `NOMAD_CONFIG_FILE` environment variable:
```bash
# Use specific config file
export NOMAD_CONFIG_FILE=/path/to/config.env
nomad --config-status

# Switch to different config
export NOMAD_CONFIG_FILE=/path/to/production-config.env
```

### Q: Can I use multiple Notion databases with one Nomad installation?
**A:** Currently, Nomad works with one database at a time. To use multiple databases:
1. **Switch configurations**: Use different config files for each database
2. **Multiple installations**: Install in different directories/environments
3. **Environment switching**: Change `NOTION_BOARD_DB` as needed

### Q: Do I need API keys for all AI providers?
**A:** No! You only need **at least one** AI provider API key:
- **OpenAI**: Most popular, good all-around performance
- **Anthropic**: Excellent for analysis and reasoning
- **OpenRouter**: Access to multiple models through one API

Nomad will automatically use available providers.

### Q: How do I keep my API keys secure?
**A:** Follow these best practices:
- **File permissions**: Set config files to 600 (owner read/write only)
- **Environment variables**: Use system environment variables in production
- **Never commit**: Don't commit API keys to version control
- **Rotate regularly**: Change API keys periodically
- **Monitor usage**: Watch for unexpected API usage

---

## Task Processing

### Q: What task statuses does Nomad support?
**A:** Nomad works with these standard statuses:
- **"To Refine"**: Tasks needing content improvement
- **"Prepare Tasks"**: Tasks to break down into subtasks
- **"Queued to run"**: Tasks ready for automated processing
- **"In Progress"**: Tasks currently being processed
- **"Done"**: Completed tasks
- **"Failed"**: Tasks that couldn't be processed

Your Notion database should have these as select options.

### Q: Can I customize the task statuses?
**A:** The status names are currently fixed, but you can:
- **Map existing statuses**: Rename your Notion select options to match
- **Use different databases**: Different databases can have different status workflows
- **Future versions**: Custom status mapping is planned for future releases

### Q: How does Nomad decide which tasks to process?
**A:** Nomad processes tasks based on:
1. **Status filtering**: Only processes specified statuses
2. **Dependency checking**: Respects task dependencies (if configured)
3. **Processing order**: Usually by creation date or database order
4. **Concurrent limits**: Processes multiple tasks simultaneously (configurable)

### Q: Why are my tasks not being processed?
**A:** Common reasons:
- **Status mismatch**: Check task status exactly matches expected values
- **Database sharing**: Ensure Notion database is shared with integration
- **Permissions**: Verify integration has "Edit" permissions
- **Content issues**: Empty tasks or invalid content may be skipped
- **API limits**: Rate limiting may delay processing

Check with:
```bash
nomad --config-status
nomad --health-check
```

### Q: How long should task processing take?
**A:** Processing time varies:
- **Simple tasks**: 10-30 seconds per task
- **Complex tasks**: 1-3 minutes per task
- **Large content**: May take longer for extensive text
- **First run**: Always slower due to setup and caching

Factors affecting speed:
- AI provider response times
- Internet connection speed
- Task complexity and size
- Concurrent processing settings

### Q: Can I process tasks in a specific order?
**A:** Currently, Nomad processes tasks in database order. For specific ordering:
- **Prioritize tasks**: Use priority properties in Notion
- **Batch processing**: Process high-priority tasks first, then others
- **Manual selection**: Process specific tasks one at a time
- **Future feature**: Custom ordering is planned

---

## Integrations

### Q: Can I use Nomad with other project management tools besides Notion?
**A:** Currently, Nomad is designed specifically for Notion. However:
- **API integration**: You can use Nomad's Python APIs with custom integrations
- **Export/import**: Use data export/import between tools
- **Future support**: Other platforms may be supported in future versions

### Q: How do I set up Slack notifications?
**A:** To enable Slack integration:
1. **Create Slack app**: Go to api.slack.com/apps
2. **Get bot token**: Create bot user and copy token
3. **Add to config**:
   ```env
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_CHANNEL_GENERAL=C1234567890
   ```
4. **Test**: Run `nomad --config-status` to verify

### Q: Can I integrate Nomad with CI/CD pipelines?
**A:** Yes! Nomad works well in automated environments:
```bash
# In CI/CD scripts
nomad --refine
nomad --prepare
nomad --multi

# Check exit codes
if [ $? -eq 0 ]; then
    echo "Processing successful"
else
    echo "Processing failed"
    exit 1
fi
```

### Q: Does Nomad work with GitHub Actions?
**A:** Absolutely! Example workflow:
```yaml
name: Process Tasks
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  process:
    runs-on: ubuntu-latest
    steps:
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install Nomad
      run: pip install nomad-notion-automation
    
    - name: Process Tasks
      env:
        NOTION_TOKEN: ${{ secrets.NOTION_TOKEN }}
        NOTION_BOARD_DB: ${{ secrets.NOTION_BOARD_DB }}
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
      run: nomad --multi
```

---

## Performance

### Q: How can I make Nomad process tasks faster?
**A:** Performance optimization tips:
1. **Use faster models**: GPT-3.5-turbo instead of GPT-4
2. **Increase concurrency**:
   ```env
   NOMAD_MAX_CONCURRENT_TASKS=5
   ```
3. **Better internet**: Faster connection = faster API calls
4. **Reduce task complexity**: Simpler tasks process faster
5. **Batch processing**: Process many tasks at once instead of one-by-one

### Q: How much do API calls cost?
**A:** Costs vary by provider and usage:
- **OpenAI GPT-3.5-turbo**: ~$0.002 per task
- **OpenAI GPT-4**: ~$0.02-0.06 per task  
- **Anthropic Claude**: ~$0.01-0.05 per task
- **OpenRouter**: Varies by model chosen

Track usage in your provider dashboards.

### Q: Can I limit API costs?
**A:** Yes, several ways:
1. **Provider limits**: Set spending limits in provider dashboards
2. **Model selection**: Use less expensive models
3. **Batch processing**: More efficient than individual requests
4. **Content size**: Smaller tasks cost less
5. **Usage monitoring**: Regular cost monitoring

### Q: Nomad seems to use a lot of memory
**A:** Memory usage can increase with:
- **Concurrent processing**: More tasks = more memory
- **Large tasks**: Big content uses more memory
- **Multiple providers**: Each provider uses memory

Optimization:
```env
# Reduce concurrent tasks
NOMAD_MAX_CONCURRENT_TASKS=2

# Use lighter models
# Configure in provider settings
```

---

## Troubleshooting

### Q: I get "nomad: command not found" after installation
**A:** This usually means the installation directory isn't in your PATH:
```bash
# Check if installed
pip show nomad-notion-automation

# Add to PATH (Linux/macOS)
export PATH=$PATH:~/.local/bin

# Make permanent
echo 'export PATH=$PATH:~/.local/bin' >> ~/.bashrc
source ~/.bashrc
```

### Q: I get "unauthorized" errors with Notion
**A:** Check these items:
1. **Token format**: Should start with `secret_`
2. **Database sharing**: Database must be shared with integration
3. **Permissions**: Integration needs "Edit" access
4. **Token validity**: Try regenerating the token

### Q: API calls are failing or timing out
**A:** Common causes and solutions:
- **Network issues**: Check internet connection
- **Rate limiting**: Wait and retry, or reduce concurrent requests
- **Invalid keys**: Verify API key format and validity
- **Service outages**: Check provider status pages
- **Firewall**: Ensure HTTPS access to API endpoints

### Q: Tasks are being processed but not updated in Notion
**A:** Troubleshooting steps:
1. **Check permissions**: Integration needs edit access
2. **Verify database ID**: Ensure correct database is configured
3. **Status transitions**: Some status changes may not be allowed
4. **Content size**: Very large content may fail to update
5. **API limits**: May be hitting Notion API rate limits

### Q: Configuration seems correct but health check fails
**A:** Try these steps:
1. **Reload config**:
   ```bash
   unset NOMAD_CONFIG_FILE
   export NOMAD_CONFIG_FILE=~/.nomad/config.env
   ```
2. **Check file permissions**:
   ```bash
   ls -la ~/.nomad/config.env
   chmod 600 ~/.nomad/config.env
   ```
3. **Validate keys manually**: Test API keys in provider dashboards
4. **Check for spaces**: Remove any trailing spaces from keys

---

## Advanced Usage

### Q: Can I run Nomad as a service/daemon?
**A:** Yes! Several approaches:
1. **Systemd** (Linux):
   ```bash
   # Create service file
   sudo nano /etc/systemd/system/nomad.service
   
   # Add service configuration
   [Unit]
   Description=Nomad Task Processor
   
   [Service]
   ExecStart=/usr/local/bin/nomad
   Restart=always
   User=nomad
   Environment=NOMAD_CONFIG_FILE=/etc/nomad/config.env
   
   [Install]
   WantedBy=multi-user.target
   ```

2. **Docker**:
   ```dockerfile
   FROM python:3.9-slim
   RUN pip install nomad-notion-automation
   CMD ["nomad"]
   ```

3. **Process managers**: PM2, supervisor, etc.

### Q: Can I customize the AI processing prompts?
**A:** Currently, prompts are built-in, but you can influence processing:
- **Task context**: Add context in task descriptions
- **Model selection**: Different models have different styles
- **Provider choice**: Each AI provider has unique characteristics
- **Future feature**: Custom prompts are planned

### Q: How do I backup my configuration and data?
**A:** Backup these items:
1. **Configuration files**:
   ```bash
   cp ~/.nomad/config.env backup/
   ```
2. **Task files** (if using local storage):
   ```bash
   cp -r ~/.nomad/tasks/ backup/
   ```
3. **Notion data**: Export from Notion as backup
4. **API keys**: Store securely in password manager

### Q: Can I extend Nomad with custom functionality?
**A:** Yes! Several extension points:
1. **Custom processors**: Create custom task processing logic
2. **API integration**: Use Nomad's Python APIs in your code
3. **Webhook integration**: Trigger Nomad from external systems
4. **Plugin system**: (Planned) Full plugin architecture

### Q: How do I migrate from one Notion database to another?
**A:** Migration steps:
1. **Export old database**: Use Notion's export feature
2. **Create new database**: Set up with same properties
3. **Import data**: Import to new database
4. **Update configuration**:
   ```env
   NOTION_BOARD_DB=new_database_id_here
   ```
5. **Test**: Run `nomad --config-status` to verify

### Q: Can multiple users/instances share the same Notion database?
**A:** Yes, but consider:
- **Concurrent processing**: Multiple instances may process same tasks
- **Task locking**: Not currently implemented
- **Status conflicts**: Race conditions possible
- **Best practice**: Use different databases or coordinate timing

---

## Still Need Help?

If your question isn't answered here:

1. **Search documentation**: Use the search function
2. **Check troubleshooting**: [Troubleshooting Guide](troubleshooting/)
3. **GitHub Discussions**: [Ask the community](https://github.com/nomad-notion-automation/nomad/discussions)
4. **GitHub Issues**: [Report bugs](https://github.com/nomad-notion-automation/nomad/issues)
5. **Documentation feedback**: Help us improve this FAQ

---

*FAQ for Nomad v0.2.0. This document is regularly updated based on community questions and feedback.*