# 🚀 Quick Start Deployment Guide

## 📋 Prerequisites

- Docker and Docker Compose installed
- JIRA API access (username and API token)
- Google Gemini API key
- Domain name (for production) or localhost (for testing)

## ⚡ 5-Minute Deployment

### **Step 1: Clone and Configure**
```bash
# Clone the repository
git clone <your-repo-url>
cd PS-ticket-bot

# Copy environment template
cp .env.production.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

### **Step 2: Configure Environment**
Edit `.env` file with your actual values:
```bash
# JIRA Configuration
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_USERNAME=your-service-account@company.com
JIRA_API_TOKEN=your-jira-api-token

# Google Gemini Configuration
GEMINI_API_KEY=your-gemini-api-key

# Security (change this!)
SECRET_KEY=your-super-secret-key-change-this
```

### **Step 3: Deploy**
```bash
# Make deployment script executable
chmod +x deploy.sh

# Deploy the application
./deploy.sh
```

### **Step 4: Verify**
```bash
# Check if services are running
docker-compose -f docker-compose.prod.yml ps

# Test health endpoint
curl http://localhost:8000/health

# View logs
./deploy.sh logs
```

## 🎯 What Gets Deployed

### **Core Services**
- **PS Ticket Bot**: Main application (port 8000)
- **Celery Worker**: Background task processing
- **Celery Beat**: Scheduled task scheduler
- **Redis**: Task queue and caching
- **PostgreSQL**: Data persistence
- **Nginx**: Reverse proxy and load balancer

### **Optional Services**
- **Prometheus**: Metrics collection (port 9090)
- **Grafana**: Metrics visualization (port 3000)

## 🔧 Configuration Options

### **Minimal Configuration (Required)**
```bash
# JIRA
JIRA_BASE_URL=https://your-company.atlassian.net
JIRA_USERNAME=service-account@company.com
JIRA_API_TOKEN=your-token

# AI
GEMINI_API_KEY=your-key

# Security
SECRET_KEY=change-this-secret
```

### **Production Configuration (Recommended)**
```bash
# All minimal settings plus:
ENVIRONMENT=production
DEBUG=false
ALLOWED_HOSTS=ps-ticket-bot.yourdomain.com
CORS_ORIGINS=https://yourdomain.com
SENTRY_DSN=your-sentry-dsn
ENABLE_METRICS=true
```

## 🌐 Access Your Deployment

### **Local Development**
- **Application**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Grafana**: http://localhost:3000 (admin/admin123)
- **Prometheus**: http://localhost:9090

### **Production URLs**
- **Application**: https://ps-ticket-bot.yourdomain.com
- **API Docs**: https://ps-ticket-bot.yourdomain.com/docs
- **Health Check**: https://ps-ticket-bot.yourdomain.com/health

## 🛠️ Management Commands

### **Deployment Management**
```bash
# Deploy/Update
./deploy.sh

# Stop services
./deploy.sh stop

# Restart services
./deploy.sh restart

# View logs
./deploy.sh logs

# Check status
./deploy.sh status

# Create backup
./deploy.sh backup

# Cleanup old images
./deploy.sh cleanup
```

### **Docker Compose Commands**
```bash
# View running services
docker-compose -f docker-compose.prod.yml ps

# View logs for specific service
docker-compose -f docker-compose.prod.yml logs -f ps-ticket-bot

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=3

# Execute commands in container
docker-compose -f docker-compose.prod.yml exec ps-ticket-bot bash
```

## 🧪 Testing Your Deployment

### **Health Checks**
```bash
# Basic health check
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health | jq

# API health check
curl http://localhost:8000/api/v1/health
```

### **JIRA Integration Test**
```bash
# Test JIRA connection
curl -X POST http://localhost:8000/api/v1/tickets/PS-1762/assess

# Test comment generation
curl -X POST http://localhost:8000/api/v1/tickets/PS-1762/comment

# Test status transition
curl -X POST http://localhost:8000/api/v1/tickets/PS-1762/transition
```

## 🔒 Security Checklist

### **Before Production**
- [ ] Change default SECRET_KEY
- [ ] Configure ALLOWED_HOSTS
- [ ] Set up SSL certificates
- [ ] Configure firewall rules
- [ ] Enable HTTPS redirect
- [ ] Set up monitoring and alerting
- [ ] Configure backup strategy
- [ ] Review and rotate API keys

### **SSL/HTTPS Setup**
```bash
# 1. Obtain SSL certificates (Let's Encrypt example)
certbot certonly --standalone -d ps-ticket-bot.yourdomain.com

# 2. Copy certificates to nginx/ssl/
mkdir -p nginx/ssl
cp /etc/letsencrypt/live/ps-ticket-bot.yourdomain.com/fullchain.pem nginx/ssl/ps-ticket-bot.crt
cp /etc/letsencrypt/live/ps-ticket-bot.yourdomain.com/privkey.pem nginx/ssl/ps-ticket-bot.key

# 3. Uncomment HTTPS server block in nginx/nginx.conf

# 4. Restart nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

## 📊 Monitoring

### **Built-in Monitoring**
- **Health Endpoint**: `/health` - Service status
- **Metrics Endpoint**: `/metrics` - Prometheus metrics
- **Logs**: Structured JSON logging

### **Grafana Dashboards**
1. Access Grafana: http://localhost:3000
2. Login: admin/admin123
3. Import PS Ticket Bot dashboard
4. Configure alerts and notifications

### **Log Monitoring**
```bash
# View application logs
./deploy.sh logs

# View specific service logs
docker-compose -f docker-compose.prod.yml logs -f celery-worker

# Monitor error logs
docker-compose -f docker-compose.prod.yml logs -f | grep ERROR
```

## 🚨 Troubleshooting

### **Common Issues**

#### **Services Won't Start**
```bash
# Check Docker status
docker --version
docker-compose --version

# Check .env file
cat .env | grep -v "^#" | grep -v "^$"

# Check logs
./deploy.sh logs
```

#### **JIRA Connection Failed**
```bash
# Test JIRA credentials
curl -u "username:api-token" "https://your-company.atlassian.net/rest/api/2/myself"

# Check environment variables
docker-compose -f docker-compose.prod.yml exec ps-ticket-bot env | grep JIRA
```

#### **AI Comments Not Working**
```bash
# Test Gemini API key
curl -H "Authorization: Bearer $GEMINI_API_KEY" "https://generativelanguage.googleapis.com/v1/models"

# Check AI service logs
docker-compose -f docker-compose.prod.yml logs -f ps-ticket-bot | grep -i gemini
```

### **Getting Help**
```bash
# View deployment status
./deploy.sh status

# Check service health
curl http://localhost:8000/health

# View recent logs
./deploy.sh logs | tail -100

# Check resource usage
docker stats
```

## 🎉 Success!

If you see this response from the health check:
```json
{
  "status": "healthy",
  "timestamp": "2025-06-18T20:00:00Z",
  "version": "1.0.0",
  "services": {
    "jira": "connected",
    "gemini": "connected",
    "redis": "connected",
    "database": "connected"
  }
}
```

**Congratulations! Your PS Ticket Process Bot is now running in production!** 🚀

## 📞 Next Steps

1. **Configure your domain and SSL**
2. **Set up monitoring and alerting**
3. **Test with real JIRA tickets**
4. **Configure scheduled tasks**
5. **Set up backup and disaster recovery**
6. **Monitor performance and scale as needed**

Your intelligent ticket processing automation is now live! 🎯
