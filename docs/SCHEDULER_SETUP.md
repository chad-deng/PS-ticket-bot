# 🕐 Scheduler Setup Guide

This guide explains how to set up and configure the scheduler for your PS Ticket Process Bot.

## 📋 Overview

The PS Ticket Process Bot uses **Celery Beat** as its scheduler to automatically trigger JIRA ticket searches based on configurable profiles. The system supports multiple scheduling strategies for different use cases.

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Celery Beat   │───▶│  Celery Worker  │───▶│   JIRA API      │
│   (Scheduler)   │    │  (Processor)    │    │   (Tickets)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Search Profiles │    │   Redis Queue   │    │  Quality Engine │
│   (Config)      │    │   (Tasks)       │    │  (Assessment)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Quick Start

### Option 1: Start All Components (Recommended)

```bash
# Start everything at once
./scripts/start-all.sh
```

This will start:
- API Server (http://localhost:8000)
- Celery Worker (task processor)
- Celery Beat (scheduler)

### Option 2: Start Components Individually

```bash
# Terminal 1: Start API Server
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Start Celery Worker
./scripts/start-celery-worker.sh

# Terminal 3: Start Celery Beat Scheduler
./scripts/start-celery-beat.sh
```

### Stop All Components

```bash
./scripts/stop-all.sh
```

## ⚙️ Configuration

### Search Profiles

Edit `config/search-profiles.yaml` to configure your search schedules:

```yaml
# Example: Search for urgent tickets every 10 minutes
urgent:
  name: "Urgent Ticket Search"
  description: "Search for high-priority tickets"
  enabled: true
  schedule: "*/10 * * * *"  # Every 10 minutes
  config:
    projects: ["PS"]
    issue_types: ["Problem", "Bug"]
    statuses: ["Open", "In Progress"]
    time_range_hours: 6
    batch_size: 20
    additional_jql: 'AND priority in ("Blocker", "P1")'
  priority: "high"
```

### Cron Schedule Format

The schedule uses standard cron format with 5 fields:

```
* * * * *
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, Sunday = 0 or 7)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

### Common Schedule Examples

| Description | Cron Expression | Usage |
|-------------|----------------|-------|
| Every 5 minutes | `*/5 * * * *` | High-frequency monitoring |
| Every 30 minutes | `*/30 * * * *` | Regular checks |
| Every hour | `0 * * * *` | Standard monitoring |
| Every 4 hours | `0 */4 * * *` | Quality reviews |
| Daily at 9 AM | `0 9 * * *` | Daily reports |
| Weekdays only | `0 9 * * 1-5` | Business hours |
| Weekends only | `0 9 * * 6,0` | Weekend monitoring |

## 🔧 Management

### API Endpoints

Check scheduler status:
```bash
curl http://localhost:8000/scheduler/status
```

List scheduled tasks:
```bash
curl http://localhost:8000/scheduler/tasks
```

Reload configuration:
```bash
curl -X POST http://localhost:8000/scheduler/reload
```

Validate cron schedule:
```bash
curl -X POST http://localhost:8000/scheduler/validate-schedule \
  -H "Content-Type: application/json" \
  -d '{"cron_schedule": "*/15 * * * *"}'
```

### Web Interface

Visit http://localhost:8000/docs for the interactive API documentation.

## 📊 Monitoring

### Log Files

When using `./scripts/start-all.sh`, logs are saved to:
- `logs/api-server.log` - API server logs
- `logs/celery-worker.log` - Worker task processing logs
- `logs/celery-beat.log` - Scheduler logs

### Real-time Monitoring

```bash
# Watch all logs
tail -f logs/*.log

# Watch scheduler logs only
tail -f logs/celery-beat.log

# Watch worker logs only
tail -f logs/celery-worker.log
```

### Process Status

```bash
# Check if processes are running
ps aux | grep celery
ps aux | grep uvicorn

# Check Redis connection
redis-cli ping
```

## 🎯 Pre-configured Profiles

The system comes with several pre-configured profiles:

### 1. Default (Every 30 minutes)
- **Purpose**: Standard monitoring
- **Targets**: Open, In Progress, Reopened tickets
- **Schedule**: `*/30 * * * *`

### 2. Urgent (Every 10 minutes)
- **Purpose**: High-priority ticket monitoring
- **Targets**: Blocker and P1 tickets
- **Schedule**: `*/10 * * * *`

### 3. New Tickets (Every 15 minutes)
- **Purpose**: Recently created tickets
- **Targets**: Newly opened tickets (last 2 hours)
- **Schedule**: `*/15 * * * *`

### 4. Reopened (Every 2 hours)
- **Purpose**: Tickets that were reopened
- **Targets**: Reopened status tickets
- **Schedule**: `0 */2 * * *`

### 5. Development (Manual)
- **Purpose**: Testing with PS-1762
- **Targets**: Cancelled tickets for testing
- **Schedule**: Manual trigger only

## 🔄 Testing

### Test with PS-1762

1. **Enable development profile**:
   ```yaml
   development:
     enabled: true
     schedule: "manual"
   ```

2. **Trigger manual search**:
   ```bash
   curl -X POST http://localhost:8000/search/trigger \
     -H "Content-Type: application/json" \
     -d '{
       "config": {
         "projects": ["PS"],
         "issue_types": ["Problem"],
         "statuses": ["Cancelled"],
         "time_range_hours": 168,
         "batch_size": 5
       },
       "priority": "normal"
     }'
   ```

3. **Check processing results**:
   ```bash
   # Get task status
   curl http://localhost:8000/search/status/{task_id}
   
   # Check worker logs
   tail -f logs/celery-worker.log
   ```

## 🛠️ Troubleshooting

### Common Issues

1. **Redis not running**:
   ```bash
   brew services start redis
   redis-cli ping  # Should return PONG
   ```

2. **Python import errors**:
   ```bash
   # Check if you can import the app
   python -c "import app.main"
   ```

3. **Schedule not loading**:
   ```bash
   # Validate search profiles
   python -c "from app.utils.search_config_manager import get_search_config_manager; print(get_search_config_manager().list_profiles())"
   ```

4. **Tasks not executing**:
   - Check if Celery worker is running
   - Verify Redis connection
   - Check search profile is enabled
   - Review logs for errors

### Debug Commands

```bash
# List Celery workers
celery -A app.core.queue inspect active

# Check scheduled tasks
celery -A app.core.queue inspect scheduled

# Purge all queues (careful!)
celery -A app.core.queue purge

# Monitor tasks in real-time
celery -A app.core.queue events
```

## 📈 Production Deployment

### Systemd Services (Linux)

Create service files for production deployment:

```ini
# /etc/systemd/system/ps-ticket-bot-worker.service
[Unit]
Description=PS Ticket Bot Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/PS-ticket-bot
ExecStart=/path/to/venv/bin/celery -A app.core.queue worker --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/ps-ticket-bot-beat.service
[Unit]
Description=PS Ticket Bot Celery Beat
After=network.target redis.service

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/PS-ticket-bot
ExecStart=/path/to/venv/bin/celery -A app.core.queue beat --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

### Docker Deployment

See `docker-compose.yml` for containerized deployment.

## 🎉 Success!

Your scheduler is now set up! The system will automatically:

1. ✅ **Fetch tickets** based on your search profiles
2. ✅ **Check required fields** for completeness
3. ✅ **Search for duplicates** to avoid redundancy
4. ✅ **Assess quality** using AI rules
5. ✅ **Add comments and transition** status based on quality

Monitor the logs and API endpoints to ensure everything is working correctly!
