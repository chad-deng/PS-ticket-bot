# Makefile for PS Ticket Process Bot

.PHONY: help setup install install-dev clean test lint format type-check security-check
.PHONY: docker-build docker-run docker-stop docker-clean
.PHONY: dev-up dev-down dev-logs dev-shell
.PHONY: validate-jira validate-gemini validate-all
.PHONY: deploy-staging deploy-production

# Default target
help:
	@echo "PS Ticket Process Bot - Available Commands:"
	@echo ""
	@echo "Setup and Installation:"
	@echo "  setup           - Initial project setup"
	@echo "  install         - Install production dependencies"
	@echo "  install-dev     - Install development dependencies"
	@echo "  clean           - Clean up temporary files and caches"
	@echo ""
	@echo "Development:"
	@echo "  dev-up          - Start development environment with Docker Compose"
	@echo "  dev-down        - Stop development environment"
	@echo "  dev-logs        - Show development environment logs"
	@echo "  dev-shell       - Open shell in development container"
	@echo "  worker          - Start Celery worker locally"
	@echo "  queue-stats     - Show queue statistics"
	@echo "  queue-purge     - Purge all queues (development only)"
	@echo ""
	@echo "Code Quality:"
	@echo "  test            - Run tests"
	@echo "  lint            - Run linting checks"
	@echo "  format          - Format code with black"
	@echo "  type-check      - Run type checking with mypy"
	@echo "  security-check  - Run security checks"
	@echo ""
	@echo "Validation:"
	@echo "  validate-config - Validate configuration files and settings"
	@echo "  validate-jira   - Validate JIRA API access"
	@echo "  validate-gemini - Validate Gemini API access"
	@echo "  validate-all    - Run all validations"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build    - Build Docker image"
	@echo "  docker-run      - Run Docker container"
	@echo "  docker-stop     - Stop Docker container"
	@echo "  docker-clean    - Clean Docker images and containers"
	@echo ""
	@echo "Deployment:"
	@echo "  deploy-staging  - Deploy to staging environment"
	@echo "  deploy-production - Deploy to production environment"

# Setup and Installation
setup:
	@echo "🚀 Setting up PS Ticket Process Bot..."
	./scripts/setup.sh

install:
	@echo "📦 Installing production dependencies..."
	pip install -r requirements.txt

install-dev:
	@echo "📦 Installing development dependencies..."
	pip install -r requirements-dev.txt

clean:
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

# Development Environment
dev-up:
	@echo "🐳 Starting development environment..."
	docker-compose up -d
	@echo "✅ Development environment started!"
	@echo "   - Bot API: http://localhost:8000"
	@echo "   - Health Check: http://localhost:8001/health"
	@echo "   - Redis: localhost:6379"
	@echo "   - PostgreSQL: localhost:5432"

dev-down:
	@echo "🛑 Stopping development environment..."
	docker-compose down

dev-logs:
	@echo "📋 Showing development environment logs..."
	docker-compose logs -f

dev-shell:
	@echo "🐚 Opening shell in development container..."
	docker-compose exec ps-bot-dev bash

# Queue Management
worker:
	@echo "👷 Starting Celery worker locally..."
	celery -A app.core.queue:celery_app worker --loglevel=info --concurrency=4 --queues=ticket_processing,quality_assessment,ai_generation,jira_operations

queue-stats:
	@echo "📊 Getting queue statistics..."
	curl -s http://localhost:8000/admin/queue/stats | python -m json.tool

queue-purge:
	@echo "🧹 Purging queues..."
	curl -X POST http://localhost:8000/admin/queue/purge

# Code Quality
test:
	@echo "🧪 Running tests..."
	pytest --cov=app --cov-report=term-missing --cov-report=html

test-watch:
	@echo "👀 Running tests in watch mode..."
	pytest-watch --runner "pytest --cov=app --cov-report=term-missing"

lint:
	@echo "🔍 Running linting checks..."
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

format:
	@echo "🎨 Formatting code..."
	black .
	isort .

format-check:
	@echo "🎨 Checking code formatting..."
	black --check --diff .
	isort --check-only --diff .

type-check:
	@echo "🔍 Running type checks..."
	mypy . --ignore-missing-imports

security-check:
	@echo "🔒 Running security checks..."
	safety check
	bandit -r . -f json

# Validation
validate-config:
	@echo "🔍 Validating configuration..."
	python scripts/validate_configuration.py

validate-jira:
	@echo "🔍 Validating JIRA API access..."
	python scripts/validate_jira_access.py

validate-gemini:
	@echo "🔍 Validating Gemini API access..."
	python scripts/validate_gemini_access.py

validate-all: validate-config validate-jira validate-gemini
	@echo "✅ All validations completed!"

# Docker
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t ps-ticket-bot:latest .

docker-build-dev:
	@echo "🐳 Building development Docker image..."
	docker build -f Dockerfile.dev -t ps-ticket-bot:dev .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run -d --name ps-ticket-bot -p 8000:8000 --env-file .env ps-ticket-bot:latest

docker-stop:
	@echo "🛑 Stopping Docker container..."
	docker stop ps-ticket-bot || true
	docker rm ps-ticket-bot || true

docker-clean:
	@echo "🧹 Cleaning Docker images and containers..."
	docker system prune -f
	docker image prune -f

# Database
db-migrate:
	@echo "🗄️ Running database migrations..."
	alembic upgrade head

db-rollback:
	@echo "🗄️ Rolling back database migration..."
	alembic downgrade -1

db-reset:
	@echo "🗄️ Resetting database..."
	alembic downgrade base
	alembic upgrade head

# Monitoring
monitoring-up:
	@echo "📊 Starting monitoring stack..."
	docker-compose --profile monitoring up -d
	@echo "✅ Monitoring started!"
	@echo "   - Prometheus: http://localhost:9090"
	@echo "   - Grafana: http://localhost:3000 (admin/admin)"

monitoring-down:
	@echo "📊 Stopping monitoring stack..."
	docker-compose --profile monitoring down

# Deployment
deploy-staging:
	@echo "🚀 Deploying to staging..."
	# Add staging deployment commands here
	@echo "⚠️  Staging deployment not yet implemented"

deploy-production:
	@echo "🚀 Deploying to production..."
	# Add production deployment commands here
	@echo "⚠️  Production deployment not yet implemented"

# Utilities
logs:
	@echo "📋 Showing application logs..."
	tail -f logs/*.log

health-check:
	@echo "🏥 Checking application health..."
	curl -f http://localhost:8000/health || echo "❌ Health check failed"

# Git hooks
install-hooks:
	@echo "🪝 Installing git hooks..."
	pre-commit install

run-hooks:
	@echo "🪝 Running git hooks on all files..."
	pre-commit run --all-files
