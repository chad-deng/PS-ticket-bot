# 🚀 Production Deployment Guide: PS Ticket Process Bot

## 📋 Overview

This guide covers deploying the PS Ticket Process Bot to production with multiple deployment options, from simple cloud hosting to enterprise Kubernetes deployments.

## 🎯 Pre-Deployment Checklist

### **✅ Code Readiness**
- [x] Phase 1 & Phase 2 features complete and tested
- [x] All fixes applied (status transitions, quality detection, concise comments)
- [x] PS-1762 comprehensive testing passed
- [x] Error handling and fallback mechanisms implemented
- [x] Configuration management ready

### **✅ Environment Requirements**
- [x] Python 3.8+ support
- [x] FastAPI web framework
- [x] Celery for background tasks
- [x] Redis for task queue and caching
- [x] PostgreSQL for data persistence (optional)
- [x] JIRA API access configured
- [x] Google Gemini API access configured

### **✅ Security Requirements**
- [x] Environment variables for sensitive data
- [x] API key management
- [x] HTTPS/TLS encryption
- [x] Authentication and authorization
- [x] Rate limiting and monitoring

## 🏗️ Deployment Options

### **Option 1: Docker Container Deployment (Recommended)**

#### **1.1 Create Production Dockerfile**
```dockerfile
# Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### **1.2 Docker Compose for Full Stack**
```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  # Main Application
  ps-ticket-bot:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:password@postgres:5432/ps_ticket_bot
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    networks:
      - ps-ticket-network

  # Celery Worker
  celery-worker:
    build: .
    command: celery -A app.core.celery worker --loglevel=info --concurrency=4
    environment:
      - ENVIRONMENT=production
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:password@postgres:5432/ps_ticket_bot
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    networks:
      - ps-ticket-network

  # Celery Beat Scheduler
  celery-beat:
    build: .
    command: celery -A app.core.celery beat --loglevel=info
    environment:
      - ENVIRONMENT=production
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=postgresql://user:password@postgres:5432/ps_ticket_bot
    depends_on:
      - redis
      - postgres
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs
    networks:
      - ps-ticket-network

  # Redis for Celery and Caching
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - ps-ticket-network

  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_DB=ps_ticket_bot
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    ports:
      - "5432:5432"
    restart: unless-stopped
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - ps-ticket-network

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - ps-ticket-bot
    restart: unless-stopped
    networks:
      - ps-ticket-network

volumes:
  redis_data:
  postgres_data:

networks:
  ps-ticket-network:
    driver: bridge
```

#### **1.3 Deploy with Docker Compose**
```bash
# Build and deploy
docker-compose -f docker-compose.prod.yml up -d

# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f ps-ticket-bot
```

### **Option 2: Cloud Platform Deployment**

#### **2.1 AWS ECS Deployment**
```json
{
  "family": "ps-ticket-bot",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "ps-ticket-bot",
      "image": "your-account.dkr.ecr.region.amazonaws.com/ps-ticket-bot:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "JIRA_API_TOKEN",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:ps-ticket-bot/jira-token"
        },
        {
          "name": "GEMINI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:ps-ticket-bot/gemini-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ps-ticket-bot",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### **2.2 Google Cloud Run Deployment**
```yaml
# cloudbuild.yaml
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/ps-ticket-bot:$COMMIT_SHA', '.']
  
  # Push the container image to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/ps-ticket-bot:$COMMIT_SHA']
  
  # Deploy container image to Cloud Run
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
    - 'run'
    - 'deploy'
    - 'ps-ticket-bot'
    - '--image'
    - 'gcr.io/$PROJECT_ID/ps-ticket-bot:$COMMIT_SHA'
    - '--region'
    - 'us-central1'
    - '--platform'
    - 'managed'
    - '--allow-unauthenticated'
```

#### **2.3 Azure Container Instances**
```bash
# Create resource group
az group create --name ps-ticket-bot-rg --location eastus

# Deploy container
az container create \
  --resource-group ps-ticket-bot-rg \
  --name ps-ticket-bot \
  --image your-registry/ps-ticket-bot:latest \
  --cpu 2 \
  --memory 4 \
  --ports 8000 \
  --environment-variables ENVIRONMENT=production \
  --secure-environment-variables \
    JIRA_API_TOKEN=$JIRA_API_TOKEN \
    GEMINI_API_KEY=$GEMINI_API_KEY
```

### **Option 3: Kubernetes Deployment**

#### **3.1 Kubernetes Manifests**
```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ps-ticket-bot

---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: ps-ticket-bot-config
  namespace: ps-ticket-bot
data:
  ENVIRONMENT: "production"
  REDIS_URL: "redis://redis-service:6379"
  LOG_LEVEL: "INFO"

---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: ps-ticket-bot-secrets
  namespace: ps-ticket-bot
type: Opaque
data:
  JIRA_API_TOKEN: <base64-encoded-token>
  GEMINI_API_KEY: <base64-encoded-key>
  JIRA_USERNAME: <base64-encoded-username>

---
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ps-ticket-bot
  namespace: ps-ticket-bot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ps-ticket-bot
  template:
    metadata:
      labels:
        app: ps-ticket-bot
    spec:
      containers:
      - name: ps-ticket-bot
        image: your-registry/ps-ticket-bot:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: ps-ticket-bot-config
        - secretRef:
            name: ps-ticket-bot-secrets
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ps-ticket-bot-service
  namespace: ps-ticket-bot
spec:
  selector:
    app: ps-ticket-bot
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ps-ticket-bot-ingress
  namespace: ps-ticket-bot
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - ps-ticket-bot.yourdomain.com
    secretName: ps-ticket-bot-tls
  rules:
  - host: ps-ticket-bot.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ps-ticket-bot-service
            port:
              number: 80
```

#### **3.2 Deploy to Kubernetes**
```bash
# Apply all manifests
kubectl apply -f k8s/

# Check deployment status
kubectl get pods -n ps-ticket-bot
kubectl get services -n ps-ticket-bot
kubectl get ingress -n ps-ticket-bot

# View logs
kubectl logs -f deployment/ps-ticket-bot -n ps-ticket-bot
```

## 🔧 Production Configuration

### **Environment Variables**
```bash
# Required Environment Variables
ENVIRONMENT=production
LOG_LEVEL=INFO

# JIRA Configuration
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_USERNAME=your-service-account@company.com
JIRA_API_TOKEN=your-jira-api-token

# Google Gemini Configuration
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-pro

# Database Configuration (if using)
DATABASE_URL=postgresql://user:password@host:5432/ps_ticket_bot

# Redis Configuration
REDIS_URL=redis://redis-host:6379

# Security
SECRET_KEY=your-secret-key-for-jwt
ALLOWED_HOSTS=ps-ticket-bot.yourdomain.com,localhost

# Monitoring
SENTRY_DSN=your-sentry-dsn-for-error-tracking
```

### **Production Settings**
```python
# app/core/config.py - Production overrides
class ProductionSettings(Settings):
    environment: str = "production"
    debug: bool = False
    log_level: str = "INFO"
    
    # Security
    allowed_hosts: List[str] = ["ps-ticket-bot.yourdomain.com"]
    cors_origins: List[str] = ["https://yourdomain.com"]
    
    # Performance
    workers: int = 4
    max_connections: int = 100
    timeout: int = 30
    
    # Monitoring
    enable_metrics: bool = True
    enable_health_checks: bool = True
```

## 📊 Monitoring and Observability

### **Health Checks**
```python
# app/api/health.py
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "version": "1.0.0",
        "services": {
            "jira": await check_jira_connection(),
            "gemini": await check_gemini_connection(),
            "redis": await check_redis_connection()
        }
    }
```

### **Metrics and Logging**
```python
# app/core/monitoring.py
import prometheus_client
from prometheus_client import Counter, Histogram, Gauge

# Metrics
REQUESTS_TOTAL = Counter('requests_total', 'Total requests', ['method', 'endpoint'])
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration')
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Active connections')
```

## 🔒 Security Considerations

### **API Security**
- Use HTTPS/TLS encryption
- Implement API key authentication
- Rate limiting and throttling
- Input validation and sanitization
- CORS configuration

### **Secret Management**
- Use cloud secret managers (AWS Secrets Manager, Azure Key Vault, etc.)
- Never commit secrets to code
- Rotate API keys regularly
- Use least privilege access

### **Network Security**
- VPC/VNET isolation
- Security groups/NSGs
- WAF protection
- DDoS protection

## 🚀 Deployment Steps

### **Step 1: Prepare Environment**
```bash
# 1. Set up production environment variables
cp .env.example .env.production
# Edit .env.production with production values

# 2. Build production image
docker build -t ps-ticket-bot:production .

# 3. Test locally with production config
docker run --env-file .env.production -p 8000:8000 ps-ticket-bot:production
```

### **Step 2: Deploy Infrastructure**
```bash
# Option A: Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# Option B: Kubernetes
kubectl apply -f k8s/

# Option C: Cloud Platform
# Follow cloud-specific deployment steps above
```

### **Step 3: Verify Deployment**
```bash
# Check health endpoint
curl https://ps-ticket-bot.yourdomain.com/health

# Test API endpoints
curl https://ps-ticket-bot.yourdomain.com/api/v1/tickets/PS-1762/assess

# Monitor logs
docker-compose logs -f ps-ticket-bot
# or
kubectl logs -f deployment/ps-ticket-bot -n ps-ticket-bot
```

### **Step 4: Configure Monitoring**
- Set up log aggregation (ELK stack, Splunk, etc.)
- Configure metrics collection (Prometheus, Grafana)
- Set up alerting (PagerDuty, Slack notifications)
- Enable error tracking (Sentry, Rollbar)

## 📈 Scaling Considerations

### **Horizontal Scaling**
- Multiple application instances
- Load balancer configuration
- Session management (stateless design)
- Database connection pooling

### **Performance Optimization**
- Redis caching for frequent queries
- Async processing with Celery
- Database query optimization
- CDN for static assets

## 🎯 Production Checklist

### **Pre-Launch**
- [ ] All environment variables configured
- [ ] SSL/TLS certificates installed
- [ ] Database migrations applied
- [ ] Health checks passing
- [ ] Monitoring and alerting configured
- [ ] Backup strategy implemented
- [ ] Security scan completed
- [ ] Load testing performed

### **Post-Launch**
- [ ] Monitor application metrics
- [ ] Check error rates and logs
- [ ] Verify JIRA integration working
- [ ] Test AI comment generation
- [ ] Validate status transitions
- [ ] Monitor resource usage
- [ ] Set up regular backups
- [ ] Document operational procedures

## 🎉 Success Metrics

### **Technical Metrics**
- Uptime: >99.9%
- Response time: <500ms
- Error rate: <1%
- CPU usage: <70%
- Memory usage: <80%

### **Business Metrics**
- Tickets processed per hour
- Comment generation success rate
- Status transition accuracy
- User satisfaction scores
- Time to resolution improvement

## 🎯 Quick Start Deployment

### **Fastest Deployment: Docker Compose**
```bash
# 1. Clone and prepare
git clone <your-repo>
cd PS-ticket-bot

# 2. Configure environment
cp .env.example .env
# Edit .env with your JIRA and Gemini credentials

# 3. Deploy with Docker Compose
docker-compose -f docker-compose.prod.yml up -d

# 4. Verify deployment
curl http://localhost:8000/health
```

### **Production-Ready Cloud Deployment**
```bash
# 1. Build and push to registry
docker build -t your-registry/ps-ticket-bot:latest .
docker push your-registry/ps-ticket-bot:latest

# 2. Deploy to cloud platform
# AWS ECS, Google Cloud Run, or Azure Container Instances
# Follow cloud-specific steps in the guide above

# 3. Configure domain and SSL
# Set up load balancer and SSL certificates

# 4. Monitor and scale
# Set up monitoring, logging, and auto-scaling
```

**Your PS Ticket Process Bot is now ready for production deployment!** 🚀
