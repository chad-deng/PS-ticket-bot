# Development Environment Setup

This guide walks you through setting up the development environment for the PS Ticket Process Bot.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git
- Make (optional, for convenience commands)

## Quick Start

1. **Clone and Setup:**
   ```bash
   git clone <repository-url>
   cd PS-ticket-bot
   make setup
   ```

2. **Configure Environment:**
   ```bash
   cp .env.template .env
   # Edit .env with your actual values
   ```

3. **Start Development Environment:**
   ```bash
   make dev-up
   ```

4. **Validate APIs:**
   ```bash
   make validate-all
   ```

## Detailed Setup

### 1. Initial Setup

Run the setup script to prepare your development environment:

```bash
./scripts/setup.sh
```

This will:
- Create Python virtual environment
- Install development dependencies
- Make scripts executable
- Create necessary directories
- Copy environment template

### 2. Environment Configuration

Edit the `.env` file with your actual configuration:

```bash
# JIRA Configuration
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_USERNAME=ps-ticket-bot
JIRA_API_TOKEN=your_jira_api_token

# Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-pro

# Bot Configuration
BOT_WEBHOOK_URL=http://localhost:8000
JIRA_WEBHOOK_SECRET=your_webhook_secret

# Database and Redis (for Docker Compose)
DATABASE_URL=postgresql://ps_bot_user:ps_bot_password@postgres:5432/ps_ticket_bot
REDIS_URL=redis://redis:6379
```

### 3. Development Environment Options

#### Option A: Docker Compose (Recommended)

Start the full development environment:

```bash
make dev-up
```

This starts:
- Bot application (with hot reload)
- Worker process
- Redis (message queue)
- PostgreSQL (database)
- Prometheus (monitoring, optional)
- Grafana (dashboards, optional)

Access points:
- **Bot API:** http://localhost:8000
- **Health Check:** http://localhost:8001/health
- **API Docs:** http://localhost:8000/docs
- **Prometheus:** http://localhost:9090 (with monitoring profile)
- **Grafana:** http://localhost:3000 (admin/admin, with monitoring profile)

#### Option B: Local Development

If you prefer to run services locally:

```bash
# Activate virtual environment
source venv/bin/activate

# Start Redis (required)
redis-server

# Start PostgreSQL (optional, can use SQLite)
# Configure DATABASE_URL accordingly

# Run the application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, run the worker
python -m app.worker
```

### 4. Validation

Validate your API access:

```bash
# Validate JIRA API
make validate-jira

# Validate Gemini API
make validate-gemini

# Run all validations
make validate-all
```

### 5. Development Workflow

#### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
pytest --cov=app --cov-report=html

# Run tests in watch mode
make test-watch
```

#### Code Quality

```bash
# Format code
make format

# Check formatting
make format-check

# Run linting
make lint

# Type checking
make type-check

# Security checks
make security-check
```

#### Database Operations

```bash
# Run migrations
make db-migrate

# Reset database
make db-reset

# Rollback migration
make db-rollback
```

## Project Structure

```
PS-ticket-bot/
├── app/                    # Main application code
│   ├── __init__.py
│   ├── main.py            # FastAPI application
│   ├── worker.py          # Celery worker
│   ├── api/               # API routes
│   ├── core/              # Core business logic
│   ├── models/            # Data models
│   ├── services/          # External service integrations
│   └── utils/             # Utility functions
├── config/                # Configuration files
│   ├── environments/      # Environment-specific configs
│   ├── jira-config.yaml   # JIRA configuration
│   └── gemini-config.yaml # Gemini configuration
├── docs/                  # Documentation
├── scripts/               # Setup and utility scripts
├── tests/                 # Test files
├── logs/                  # Log files (created at runtime)
├── docker-compose.yml     # Development environment
├── Dockerfile             # Production container
├── Dockerfile.dev         # Development container
├── Makefile              # Development commands
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
└── .env.template         # Environment template
```

## Environment-Specific Configurations

The bot supports multiple environments with specific configurations:

- **Development:** `config/environments/development.yaml`
- **Staging:** `config/environments/staging.yaml`
- **Production:** `config/environments/production.yaml`

Set the `ENVIRONMENT` variable to load the appropriate configuration.

## Monitoring and Observability

### Prometheus Metrics

The bot exposes metrics at `/metrics` endpoint:
- Request counts and durations
- Queue depth and processing times
- API call success/failure rates
- Custom business metrics

### Health Checks

Health check endpoint at `/health` provides:
- Application status
- Database connectivity
- Redis connectivity
- External API status

### Logging

Structured logging with different levels:
- **DEBUG:** Detailed information for debugging
- **INFO:** General information about application flow
- **WARNING:** Warning messages for potential issues
- **ERROR:** Error messages for failures

## Troubleshooting

### Common Issues

**1. Port Already in Use**
```bash
# Find and kill process using port 8000
lsof -ti:8000 | xargs kill -9
```

**2. Docker Permission Issues**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Logout and login again
```

**3. Database Connection Issues**
```bash
# Reset Docker volumes
docker-compose down -v
docker-compose up -d
```

**4. API Validation Failures**
- Check environment variables in `.env`
- Verify API keys and permissions
- Check network connectivity

### Getting Help

1. Check application logs: `make logs`
2. Check Docker logs: `make dev-logs`
3. Run health check: `make health-check`
4. Review configuration files
5. Check GitHub issues for known problems

## Next Steps

After successful setup:

1. **Explore the API:** Visit http://localhost:8000/docs
2. **Run Tests:** `make test`
3. **Start Development:** Begin implementing Phase 1 tasks
4. **Set up Monitoring:** `make monitoring-up`
5. **Configure IDE:** Set up your preferred IDE with the virtual environment

## IDE Configuration

### VS Code

Recommended extensions:
- Python
- Pylance
- Black Formatter
- GitLens
- Docker

Settings (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.testing.pytestEnabled": true
}
```

### PyCharm

1. Open project in PyCharm
2. Configure Python interpreter: `./venv/bin/python`
3. Set up run configurations for FastAPI and Celery
4. Configure code style to use Black formatter
