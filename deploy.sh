#!/bin/bash

# PS Ticket Process Bot - Production Deployment Script
# This script helps deploy the PS Ticket Process Bot to production

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env"
BACKUP_DIR="./backups"
LOG_DIR="./logs"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if .env file exists
    if [ ! -f "$ENV_FILE" ]; then
        log_error ".env file not found. Please copy .env.production.example to .env and configure it."
        exit 1
    fi
    
    # Check if docker-compose.prod.yml exists
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "$COMPOSE_FILE not found."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p "./nginx"
    mkdir -p "./monitoring"
    
    log_success "Directories created"
}

backup_existing() {
    log_info "Creating backup of existing deployment..."
    
    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        BACKUP_NAME="backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR/$BACKUP_NAME"
        
        # Backup database
        docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U psticket ps_ticket_bot > "$BACKUP_DIR/$BACKUP_NAME/database.sql" 2>/dev/null || log_warning "Database backup failed"
        
        # Backup logs
        cp -r "$LOG_DIR" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || log_warning "Log backup failed"
        
        log_success "Backup created: $BACKUP_NAME"
    else
        log_info "No existing deployment found, skipping backup"
    fi
}

build_images() {
    log_info "Building Docker images..."
    
    docker-compose -f "$COMPOSE_FILE" build --no-cache
    
    log_success "Docker images built successfully"
}

deploy() {
    log_info "Deploying PS Ticket Process Bot..."
    
    # Stop existing containers
    docker-compose -f "$COMPOSE_FILE" down
    
    # Start new deployment
    docker-compose -f "$COMPOSE_FILE" up -d
    
    log_success "Deployment started"
}

wait_for_services() {
    log_info "Waiting for services to be ready..."
    
    # Wait for main application
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health &> /dev/null; then
            log_success "Application is ready"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "Application failed to start within expected time"
            exit 1
        fi
        
        log_info "Waiting for application... (attempt $attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    done
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    # Check if all services are running
    if ! docker-compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_error "Some services are not running"
        docker-compose -f "$COMPOSE_FILE" ps
        exit 1
    fi
    
    # Test health endpoint
    if ! curl -f http://localhost:8000/health &> /dev/null; then
        log_error "Health check failed"
        exit 1
    fi
    
    # Test API endpoint
    if ! curl -f http://localhost:8000/api/v1/health &> /dev/null; then
        log_warning "API health check failed, but main health check passed"
    fi
    
    log_success "Deployment verification passed"
}

show_status() {
    log_info "Deployment Status:"
    echo ""
    docker-compose -f "$COMPOSE_FILE" ps
    echo ""
    
    log_info "Service URLs:"
    echo "  - Application: http://localhost:8000"
    echo "  - Health Check: http://localhost:8000/health"
    echo "  - API Documentation: http://localhost:8000/docs"
    echo "  - Grafana (if enabled): http://localhost:3000"
    echo "  - Prometheus (if enabled): http://localhost:9090"
    echo ""
    
    log_info "Useful Commands:"
    echo "  - View logs: docker-compose -f $COMPOSE_FILE logs -f"
    echo "  - Stop services: docker-compose -f $COMPOSE_FILE down"
    echo "  - Restart services: docker-compose -f $COMPOSE_FILE restart"
    echo "  - Update deployment: ./deploy.sh"
}

cleanup() {
    log_info "Cleaning up old Docker images..."
    docker image prune -f
    log_success "Cleanup completed"
}

# Main deployment process
main() {
    echo "🚀 PS Ticket Process Bot - Production Deployment"
    echo "================================================"
    
    check_prerequisites
    create_directories
    backup_existing
    build_images
    deploy
    wait_for_services
    verify_deployment
    cleanup
    show_status
    
    echo ""
    log_success "🎉 Deployment completed successfully!"
    echo ""
    log_info "Next steps:"
    echo "  1. Configure your domain and SSL certificates"
    echo "  2. Set up monitoring and alerting"
    echo "  3. Test the JIRA integration"
    echo "  4. Monitor the logs for any issues"
    echo ""
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "stop")
        log_info "Stopping PS Ticket Process Bot..."
        docker-compose -f "$COMPOSE_FILE" down
        log_success "Services stopped"
        ;;
    "restart")
        log_info "Restarting PS Ticket Process Bot..."
        docker-compose -f "$COMPOSE_FILE" restart
        log_success "Services restarted"
        ;;
    "logs")
        docker-compose -f "$COMPOSE_FILE" logs -f
        ;;
    "status")
        show_status
        ;;
    "backup")
        backup_existing
        ;;
    "cleanup")
        cleanup
        ;;
    "help")
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  deploy   - Deploy the application (default)"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  logs     - Show and follow logs"
        echo "  status   - Show deployment status"
        echo "  backup   - Create backup of current deployment"
        echo "  cleanup  - Clean up old Docker images"
        echo "  help     - Show this help message"
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
