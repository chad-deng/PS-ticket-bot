# Setup Scripts

This directory contains setup and validation scripts for the PS Ticket Process Bot.

## Scripts Overview

### `setup.sh`
Main setup script that prepares the development environment.

**Usage:**
```bash
./scripts/setup.sh
```

**What it does:**
- Creates Python virtual environment
- Installs development dependencies
- Makes scripts executable
- Creates .env file from template
- Creates necessary directories

### `validate_jira_access.py`
Validates JIRA API connectivity, permissions, and configuration.

**Usage:**
```bash
# After running setup.sh and configuring .env
source venv/bin/activate
python scripts/validate_jira_access.py
```

**What it validates:**
- JIRA API connectivity
- Project access permissions
- Issue type discovery
- Custom field mapping
- Required permissions

**Output:**
- Validation results in console
- Updated configuration file: `config/jira-config-updated.yaml`

### `setup_jira_webhooks.py`
Sets up JIRA webhooks for the bot.

**Usage:**
```bash
# After validating JIRA access
source venv/bin/activate
python scripts/setup_jira_webhooks.py
```

**What it does:**
- Lists existing webhooks
- Creates new webhook for the bot
- Validates webhook permissions
- Tests webhook endpoint connectivity

### `validate_configuration.py`
Validates all configuration files and settings.

**Usage:**
```bash
# After setting up environment
source venv/bin/activate
python scripts/validate_configuration.py
```

**What it validates:**
- Environment variables
- Configuration file syntax
- Pydantic settings validation
- JIRA field mappings
- Transition configurations
- Feature flag consistency

## Setup Process

1. **Initial Setup:**
   ```bash
   ./scripts/setup.sh
   ```

2. **Configure Environment:**
   Edit `.env` file with your actual values:
   ```bash
   nano .env
   ```

3. **Validate Configuration:**
   ```bash
   source venv/bin/activate
   python scripts/validate_configuration.py
   ```

4. **Validate JIRA Access:**
   ```bash
   python scripts/validate_jira_access.py
   ```

5. **Setup Webhooks:**
   ```bash
   python scripts/setup_jira_webhooks.py
   ```

## Environment Variables Required

The scripts require the following environment variables to be set in `.env`:

### JIRA Configuration
- `JIRA_BASE_URL`: Your JIRA instance URL
- `JIRA_USERNAME`: Bot service account username
- `JIRA_API_TOKEN`: API token for authentication

### Bot Configuration
- `BOT_WEBHOOK_URL`: URL where the bot will be deployed
- `JIRA_WEBHOOK_SECRET`: Secret for webhook authentication

### Optional
- `GEMINI_API_KEY`: Google Gemini API key (for later phases)

## Troubleshooting

### Common Issues

**1. Permission Denied on Scripts**
```bash
chmod +x scripts/*.py scripts/*.sh
```

**2. Python Virtual Environment Issues**
```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

**3. JIRA API Authentication Errors**
- Verify JIRA_BASE_URL format: `https://company.atlassian.net`
- Ensure API token is valid and not expired
- Check that bot user has necessary permissions

**4. Webhook Creation Fails**
- Ensure bot user has "Administer Projects" permission
- Verify BOT_WEBHOOK_URL is accessible
- Check if webhook already exists

### Getting Help

1. Check the validation output for specific error messages
2. Review JIRA permissions for the bot user
3. Verify environment variable values in `.env`
4. Check JIRA administrator documentation

## Next Steps

After successful setup:

1. Review `config/jira-config-updated.yaml` for discovered values
2. Update main configuration files with correct IDs
3. Proceed to Phase 0.3: LLM API Access
4. Begin Phase 0.4: Environment Setup
