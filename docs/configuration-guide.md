# Configuration Guide

This guide explains how to configure the PS Ticket Process Bot for different environments and use cases.

## Configuration Overview

The bot uses a multi-layered configuration system:

1. **Environment Variables** - For secrets and environment-specific settings
2. **YAML Configuration Files** - For structured configuration and rules
3. **Pydantic Settings** - For type validation and defaults
4. **Runtime Configuration** - For dynamic configuration management

## Configuration Files

### Environment-Specific Configurations

Located in `config/environments/`:

- `development.yaml` - Development environment settings
- `staging.yaml` - Staging environment settings  
- `production.yaml` - Production environment settings

The appropriate file is loaded based on the `ENVIRONMENT` environment variable.

### Service-Specific Configurations

- `config/jira-config.yaml` - JIRA integration settings
- `config/gemini-config.yaml` - Gemini API settings

## Environment Variables

### Required Variables

```bash
# JIRA Configuration
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_USERNAME=ps-ticket-bot
JIRA_API_TOKEN=your_jira_api_token

# Gemini API Configuration  
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-pro

# Security
SECRET_KEY=your_secret_key_here
JIRA_WEBHOOK_SECRET=your_webhook_secret

# Environment
ENVIRONMENT=development  # development, staging, production
```

### Optional Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# Redis
REDIS_URL=redis://localhost:6379

# Application
DEBUG=false
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# Feature Flags
ENABLE_WEBHOOKS=true
ENABLE_AI_COMMENTS=true
ENABLE_STATUS_TRANSITIONS=true
ENABLE_NOTIFICATIONS=true

# Quality Rules
QUALITY_SUMMARY_MIN_LENGTH=10
QUALITY_DESCRIPTION_MIN_LENGTH=50
QUALITY_HIGH_MAX_ISSUES=1
QUALITY_MEDIUM_MAX_ISSUES=3

# API Timeouts
JIRA_TIMEOUT=30
GEMINI_TIMEOUT=30
JIRA_MAX_RETRIES=3
GEMINI_MAX_RETRIES=3

# Monitoring
MONITORING_ENABLE_PROMETHEUS=true
MONITORING_PROMETHEUS_PORT=8001
```

## Configuration Sections

### Application Settings

```yaml
app:
  name: "PS Ticket Process Bot"
  version: "0.1.0"
  environment: "development"
  debug: false
  host: "0.0.0.0"
  port: 8000
```

### JIRA Integration

```yaml
jira:
  base_url: "${JIRA_BASE_URL}"
  username: "${JIRA_USERNAME}"
  api_token: "${JIRA_API_TOKEN}"
  timeout: 30
  max_retries: 3
  
  # Project Configuration
  projects:
    primary:
      key: "SUPPORT"
      name: "Product Support"
      
  # Issue Types
  issue_types:
    - name: "Bug"
      process: true
    - name: "Support Request"
      process: true
      
  # Field Mappings
  fields:
    standard:
      summary: "summary"
      description: "description"
    custom:
      steps_to_reproduce: "customfield_10001"
      affected_version: "customfield_10002"
      
  # Status Transitions
  transitions:
    high_quality:
      - target_status: "In Progress"
        transition_id: "11"
    medium_quality:
      - target_status: "Awaiting Customer Info"
        transition_id: "21"
```

### Gemini API Configuration

```yaml
gemini:
  api_key: "${GEMINI_API_KEY}"
  model: "gemini-pro"
  
  # Generation Parameters
  generation_config:
    temperature: 0.3
    top_p: 0.8
    top_k: 40
    max_output_tokens: 1024
    
  # Safety Settings
  safety_settings:
    - category: "HARM_CATEGORY_HARASSMENT"
      threshold: "BLOCK_MEDIUM_AND_ABOVE"
```

### Quality Assessment Rules

```yaml
quality_rules:
  summary:
    min_length: 10
    max_length: 255
    required: true
    
  description:
    min_length: 50
    required: true
    
  steps_to_reproduce:
    min_length: 20
    required_for_issue_types: ["Bug"]
    
  affected_version:
    required: true
    
  attachments:
    recommended_for_issue_types: ["Bug"]
    
  high_priority_validation:
    enforce_all_rules: true
    priority_levels: ["Highest", "High"]

# Quality Scoring
quality_scoring:
  high_quality:
    max_issues: 1
  medium_quality:
    max_issues: 3
  low_quality:
    min_issues: 4
```

### Feature Flags

```yaml
features:
  enable_webhooks: true
  enable_polling: false
  enable_ai_comments: true
  enable_status_transitions: true
  enable_notifications: true
  enable_metrics: true
```

### Monitoring Configuration

```yaml
monitoring:
  enable_prometheus: true
  prometheus_port: 8001
  health_check_interval: 30
  metrics_prefix: "ps_ticket_bot"
  
  alert_thresholds:
    error_rate: 0.05  # 5%
    response_time_p95: 5.0  # 5 seconds
    queue_depth: 1000
```

## Configuration Validation

### Validate Configuration

```bash
# Validate all configuration
python scripts/validate_configuration.py

# Validate specific APIs
python scripts/validate_jira_access.py
python scripts/validate_gemini_access.py
```

### Runtime Validation

The bot automatically validates configuration at startup and provides detailed error messages for any issues.

## Environment-Specific Settings

### Development Environment

- Debug mode enabled
- Verbose logging
- Auto-reload enabled
- Status transitions disabled for safety
- Mock external APIs (optional)

### Staging Environment

- Production-like settings
- Limited processing
- Enhanced monitoring
- Test notifications

### Production Environment

- Optimized performance settings
- Full feature set enabled
- Comprehensive monitoring
- Production notifications

## Configuration Management

### Loading Configuration

```python
from app.core.config import get_settings

settings = get_settings()

# Access configuration
jira_url = settings.jira.base_url
enable_ai = settings.features.enable_ai_comments
```

### Runtime Configuration Changes

```python
from app.utils.config_manager import get_config_manager

config_manager = get_config_manager()

# Check if issue type should be processed
should_process = config_manager.should_process_issue_type("Bug")

# Get transition for quality level
transition = config_manager.get_transition_for_quality("high")

# Get field mapping
field_id = config_manager.get_field_mapping("steps_to_reproduce")
```

### Configuration Export

```python
# Export configuration (without secrets)
config_yaml = config_manager.export_config("yaml", include_secrets=False)

# Export with secrets (for backup/migration)
config_json = config_manager.export_config("json", include_secrets=True)
```

## Security Considerations

### Secrets Management

1. **Never commit secrets to version control**
2. **Use environment variables for sensitive data**
3. **Rotate API keys regularly**
4. **Use secrets managers in production**

### Configuration Security

```bash
# Set restrictive permissions on config files
chmod 600 .env
chmod 644 config/*.yaml

# Use environment-specific secrets
# Development
export JIRA_API_TOKEN="dev_token"

# Production  
export JIRA_API_TOKEN="$(aws secretsmanager get-secret-value --secret-id prod/jira-token --query SecretString --output text)"
```

## Troubleshooting

### Common Configuration Issues

**1. Missing Environment Variables**
```
❌ Missing required environment variables: JIRA_API_TOKEN
```
Solution: Set the missing environment variable in `.env` file

**2. Invalid YAML Syntax**
```
❌ config/jira-config.yaml: Invalid YAML - mapping values are not allowed here
```
Solution: Check YAML indentation and syntax

**3. Pydantic Validation Errors**
```
❌ Pydantic validation error: temperature must be between 0.0 and 1.0
```
Solution: Fix the invalid configuration value

**4. Field Mapping Issues**
```
⚠️ Missing field mappings: steps_to_reproduce
```
Solution: Add the missing field mapping to JIRA configuration

### Configuration Debugging

```bash
# Check current configuration
python -c "
from app.core.config import get_settings
settings = get_settings()
print(f'Environment: {settings.app.environment}')
print(f'JIRA URL: {settings.jira.base_url}')
print(f'Features: {settings.features.__dict__}')
"

# Validate configuration
make validate-all

# Export configuration for review
python -c "
from app.utils.config_manager import get_config_manager
cm = get_config_manager()
print(cm.export_config('yaml'))
"
```

## Best Practices

### Configuration Organization

1. **Use environment-specific files** for different deployment environments
2. **Group related settings** in logical sections
3. **Use descriptive names** for configuration keys
4. **Document configuration options** with comments
5. **Validate configuration** before deployment

### Environment Management

1. **Use `.env` files** for local development
2. **Use secrets managers** for production
3. **Separate configuration** from code
4. **Version control** configuration templates
5. **Test configuration changes** in staging first

### Security Best Practices

1. **Never log sensitive configuration** values
2. **Use least privilege** for API tokens
3. **Rotate secrets regularly**
4. **Audit configuration access**
5. **Encrypt configuration** at rest in production
