Check if Task Master is installed and install it if needed.

This command helps you get Task Master set up globally on your system.

## Detection and Installation Process

1. **Check Current Installation**
   ```bash
   # Check if taskmaster command exists
   which taskmaster || echo "Task Master not found"
   
   # Check npm global packages
   npm list -g taskmaster-ai
   ```

2. **System Requirements Check**
   ```bash
   # Verify Node.js is installed
   node --version
   
   # Verify npm is installed  
   npm --version
   
   # Check Node version (need 16+)
   ```

3. **Install Task Master Globally**
   If not installed, run:
   ```bash
   npm install -g taskmaster-ai
   ```

4. **Verify Installation**
   ```bash
   # Check version
   taskmaster --version
   
   # Verify command is available
   which taskmaster
   ```

5. **Initial Setup**
   ```bash
   # Initialize in current directory
   taskmaster init
   ```

6. **Configure AI Provider**
   Ensure you have at least one AI provider API key set:
   ```bash
   # Check current configuration
   taskmaster models --status
   
   # If no API keys found, guide setup
   echo "You'll need at least one API key:"
   echo "- ANTHROPIC_API_KEY for Claude"
   echo "- OPENAI_API_KEY for GPT models"
   echo "- PERPLEXITY_API_KEY for research"
   echo ""
   echo "Set them in your shell profile or .env file"
   ```

7. **Quick Test**
   ```bash
   # Create a test PRD
   echo "Build a simple hello world API" > test-prd.txt
   
   # Try parsing it
   taskmaster parse-prd test-prd.txt -n 3
   ```

## Troubleshooting

If installation fails:

**Permission Errors:**
```bash
# Try with sudo (macOS/Linux)
sudo npm install -g taskmaster-ai

# Or fix npm permissions
npm config set prefix ~/.npm-global
export PATH=~/.npm-global/bin:$PATH
```

**Network Issues:**
```bash
# Use different registry
npm install -g taskmaster-ai --registry https://registry.npmjs.org/
```

**Node Version Issues:**
```bash
# Install Node 18+ via nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18
```

## Success Confirmation

Once installed, you should see:
```
✅ Task Master v0.16.2 (or higher) installed
✅ Command 'taskmaster' available globally
✅ AI provider configured
✅ Ready to use slash commands!

Try: /project:taskmaster:init your-prd.md
```

## Next Steps

After installation:
1. Run `/project:utils:check-health` to verify setup
2. Configure AI providers with `/project:taskmaster:models`
3. Start using Task Master commands!