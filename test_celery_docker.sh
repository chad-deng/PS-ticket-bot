
# Test Celery worker
docker-compose -f docker-compose.prod.yml run --rm celery-worker celery -A app.core.celery inspect registered

# Test Celery beat
docker-compose -f docker-compose.prod.yml run --rm celery-beat celery -A app.core.celery inspect scheduled

# Start services for testing
docker-compose -f docker-compose.prod.yml up -d redis postgres
docker-compose -f docker-compose.prod.yml up celery-worker celery-beat
