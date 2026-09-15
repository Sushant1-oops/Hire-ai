# 🚀 AI Semantic Hiring Assistant - Deployment Guide

Complete, production-ready deployment instructions for various platforms.

---

## Table of Contents
1. [Local Development](#local-development)
2. [Docker Deployment](#docker-deployment)
3. [AWS Deployment](#aws-deployment)
4. [DigitalOcean Deployment](#digitalocean-deployment)
5. [Google Cloud Deployment](#google-cloud-deployment)
6. [Heroku Deployment](#heroku-deployment)
7. [Production Best Practices](#production-best-practices)
8. [Monitoring & Maintenance](#monitoring--maintenance)

---

## Local Development

### Prerequisites
- Python 3.11+
- Git
- Ollama
- ~4GB RAM minimum

### Step-by-Step Setup

#### 1. Clone Repository
```bash
git clone <repository-url>
cd ai_hr_saas
```

#### 2. Create Python Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Setup Environment Variables
```bash
# Copy example file
cp .env.example .env

# Edit .env with your settings
# Especially change SECRET_KEY
```

#### 5. Initialize Database
```bash
cd backend
python database.py
cd ..
```

#### 6. Start Ollama
```bash
# Download and install Ollama from https://ollama.ai

# Start Ollama service
ollama serve

# In another terminal, pull the model
ollama pull llama3.2:3b
```

#### 7. Start Backend
```bash
cd backend
python main.py
# Server runs on http://localhost:8000
```

#### 8. Start Frontend (New Terminal)
```bash
streamlit run frontend/streamlit_app.py
# UI runs on http://localhost:8501
```

#### 9. Verify Installation
```bash
# Check Backend Health
curl http://localhost:8000/health

# Check API Docs
# Open http://localhost:8000/docs

# Test Ollama
curl http://localhost:11434/api/tags

# Access Frontend
# Open http://localhost:8501
```

---

## Docker Deployment

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+

### Single Container Deployment

#### 1. Build Image
```bash
docker build -t ai-hr-saas:latest .
```

#### 2. Run Container
```bash
docker run -it \
  -p 8000:8000 \
  -p 8501:8501 \
  -e OLLAMA_API_URL=http://host.docker.internal:11434 \
  -v $(pwd)/data:/app/data \
  --name ai-hr-saas \
  ai-hr-saas:latest
```

Note: `host.docker.internal` works on Docker Desktop; adjust for VMs.

### Multi-Container Deployment (Recommended)

#### 1. Using Docker Compose
```bash
# Build all services
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### 2. Deploy with Environment File
```bash
# Create .env.production
echo "SECRET_KEY=your-production-secret" > .env.production

# Run with specific env file
docker-compose --env-file .env.production up -d
```

#### 3. Scale Services (with Nginx)
```bash
# Update docker-compose.yml to add load balancer
# Then scale backend service
docker-compose up -d --scale backend=3
```

#### 4. Verify Deployment
```bash
docker-compose ps
docker-compose logs api
docker exec ai_hr_backend curl http://localhost:8000/health
```

#### 5. Common Docker Commands
```bash
# View container status
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Execute command in container
docker-compose exec backend python backend/database.py

# Restart service
docker-compose restart backend

# Rebuild service
docker-compose up -d --build backend

# Remove everything
docker-compose down -v
```

---

## AWS Deployment

### Option A: AWS ECS (Elastic Container Service)

#### Prerequisites
- AWS Account
- AWS CLI configured
- ECR repository created

#### Step 1: Push Images to ECR
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin {ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

# Build and tag images
docker build -t ai-hr-backend:latest .
docker tag ai-hr-backend:latest {ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/ai-hr-backend:latest
docker push {ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/ai-hr-backend:latest

# Repeat for frontend
docker build -f Dockerfile.frontend -t ai-hr-frontend:latest .
docker tag ai-hr-frontend:latest {ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/ai-hr-frontend:latest
docker push {ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/ai-hr-frontend:latest
```

#### Step 2: Create ECS Cluster
```bash
aws ecs create-cluster --cluster-name ai-hr-production

# Register task definitions
aws ecs register-task-definition --cli-input-json file://backend-task-definition.json
aws ecs register-task-definition --cli-input-json file://frontend-task-definition.json
```

#### Step 3: Create ECS Services
```bash
aws ecs create-service \
  --cluster ai-hr-production \
  --service-name ai-hr-backend \
  --task-definition ai-hr-backend:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}"
```

#### Step 4: Setup RDS PostgreSQL
```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier ai-hr-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username admin \
  --master-user-password {STRONG_PASSWORD} \
  --allocated-storage 20

# Update DATABASE_URL in task definition
# DATABASE_URL=postgresql://admin:password@ai-hr-db.xxx.us-east-1.rds.amazonaws.com:5432/ai_hr_saas
```

### Option B: AWS Elastic Beanstalk

#### Step 1: Install EB CLI
```bash
pip install awsebcli
```

#### Step 2: Initialize Application
```bash
eb init -p docker ai-hr-saas
```

#### Step 3: Create Environment
```bash
eb create ai-hr-production
```

#### Step 4: Deploy
```bash
eb deploy
```

#### Step 5: Monitor
```bash
eb open
eb logs
eb status
```

### Option C: AWS App Runner

#### Step 1: Push to ECR (same as above)

#### Step 2: Create App Runner Service via Console
- Service name: `ai-hr-backend`
- Image: ECR repository URL
- Port: 8000
- Environment variables: Add from .env

---

## DigitalOcean Deployment

### Option A: Docker Container

#### 1. Create Droplet
```bash
# Create 2GB RAM, Ubuntu 22.04 LTS droplet
# Install Docker on creation
```

#### 2. SSH Into Droplet
```bash
ssh root@{DROPLET_IP}
```

#### 3. Clone Repository
```bash
git clone <repository-url>
cd ai_hr_saas
```

#### 4. Create Production Environment
```bash
cp .env.example .env
# Edit .env with production settings
```

#### 5. Start Services with Docker Compose
```bash
docker-compose -f docker-compose.prod.yml up -d
```

#### 6. Setup Nginx Reverse Proxy
```bash
# Install Nginx
apt-get update
apt-get install nginx -y

# Create config file
cat > /etc/nginx/sites-available/ai-hr <<EOF
upstream backend {
    server localhost:8000;
}

upstream frontend {
    server localhost:8501;
}

server {
    listen 80;
    server_name your-domain.com;

    location /api {
        proxy_pass http://backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }

    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

# Enable config
ln -s /etc/nginx/sites-available/ai-hr /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

#### 7. Setup SSL with Let's Encrypt
```bash
apt-get install certbot python3-certbot-nginx -y
certbot --nginx -d your-domain.com
```

### Option B: DigitalOcean App Platform

#### 1. Connect GitHub
- In DigitalOcean console, click "Create" → "App"
- Select repository

#### 2. Configure Components
```yaml
services:
- name: backend
  github:
    repo: your-repo
  build_command: pip install -r requirements.txt
  run_command: python backend/main.py
  http_port: 8000

- name: frontend
  github:
    repo: your-repo
  build_command: pip install -r requirements.txt
  run_command: streamlit run frontend/streamlit_app.py
  http_port: 8501
```

#### 3. Add Database
- Click "Add Resource" → PostgreSQL
- Configure connection

#### 4. Deploy
- Platform auto-deploys on GitHub push

---

## Google Cloud Deployment

### Using Google Cloud Run

#### 1. Setup GCP Project
```bash
gcloud init
gcloud config set project PROJECT_ID
```

#### 2. Enable Required Services
```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudkms.googleapis.com
```

#### 3. Build and Push to Artifact Registry
```bash
# Build locally
gcloud builds submit --tag gcr.io/PROJECT_ID/ai-hr-backend

# Deploy to Cloud Run
gcloud run deploy ai-hr-backend \
  --image gcr.io/PROJECT_ID/ai-hr-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OLLAMA_API_URL=http://ollama-service:11434 \
  --memory 2Gi
```

#### 4. Setup Cloud SQL (PostgreSQL)
```bash
# Create Cloud SQL instance
gcloud sql instances create ai-hr-db \
  --database-version POSTGRES_15 \
  --tier db-f1-micro \
  --region us-central1

# Create database
gcloud sql databases create ai_hr_saas \
  --instance ai-hr-db

# Create user
gcloud sql users create hr_user \
  --instance ai-hr-db \
  --password
```

#### 5. Update Connection String
```bash
# Get connection string
DATABASE_URL=postgresql://hr_user:PASSWORD@HOST/ai_hr_saas
```

---

## Heroku Deployment

### Step 1: Install Heroku CLI
```bash
curl https://cli.heroku.com/install.sh | sh
heroku login
```

### Step 2: Create Heroku App
```bash
heroku create ai-hr-assistant
```

### Step 3: Add PostgreSQL Addon
```bash
heroku addons:create heroku-postgresql:standard-0 -a ai-hr-assistant
```

### Step 4: Deploy
```bash
git push heroku main
```

### Step 5: Initialize Database
```bash
heroku run python backend/database.py -a ai-hr-assistant
```

### Step 6: View Application
```bash
heroku open -a ai-hr-assistant
```

---

## Production Best Practices

### 1. Environment Configuration
```bash
# Use strong random SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set production environment
ENV=production

# Disable debug mode
DEBUG=False
```

### 2. Database Security
- Use managed databases (RDS, Cloud SQL)
- Enable encryption at rest
- Enable encryption in transit (SSL/TLS)
- Regular backups
- Restricted network access

### 3. API Security
```python
# In production, update settings:
- CORS_ORIGINS = ["https://your-domain.com"]
- ALLOWED_HOSTS = ["your-domain.com"]
- SECURE_COOKIES = True
- CSRF_ENABLED = True
```

### 4. SSL/TLS Configuration
- Use Let's Encrypt for free certificates
- Enforce HTTPS redirect
- HSTS headers enabled
- Certificate auto-renewal

### 5. Logging & Monitoring
```bash
# Setup structured logging
python -c "
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('production.log'),
        logging.StreamHandler()
    ]
)
"

# Monitor with CloudWatch/Stackdriver
# Setup alerts for errors, timeouts
```

### 6. Rate Limiting
```bash
# Install slowapi
pip install slowapi

# Add to main.py
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
```

### 7. Resource Optimization
```bash
# Production Docker settings
- CPU limits: 1-2 cores per container
- Memory limits: 1-2GB per container
- Autoscaling: Min 2, Max 10 instances
```

### 8. Backup Strategy
```bash
# Daily backups
*/0 0 * * * mysqldump -u {user} -p{password} ai_hr_saas > backup_$(date +\%Y\%m\%d).sql

# Weekly AWS S3 upload
*/0 0 * * 0 aws s3 sync ./backups s3://ai-hr-backups/
```

---

## Monitoring & Maintenance

### Health Checks
```bash
# Setup monitoring
curl http://api.your-domain.com/health

# Expected response
{
  "status": "healthy",
  "timestamp": "2024-01-20T10:30:00",
  "ollama": "connected"
}
```

### Metrics Dashboard
- Request latency (p50, p95, p99)
- Error rate
- API usage
- Database connections
- CPU/Memory utilization

### Log Analysis
```bash
# View logs
docker-compose logs -f backend

# Filter by log level
docker-compose logs backend | grep "ERROR"

# Ship to ELK/Splunk
# Configure log driver in docker-compose.yml
```

### Performance Tuning
```bash
# Database query optimization
# Index frequently searched columns

# FAISS index optimization
# Rebuild index after every 1000 new resumes

# API response caching
# Cache job descriptions and system prompts
```

### Regular Maintenance
```bash
# Weekly
- Check error logs
- Monitor disk space
- Verify backups

# Monthly
- Update dependencies
- Review security patches
- Performance analysis

# Quarterly
- Security audit
- Database optimization
- Disaster recovery test
```

---

## Troubleshooting Deployment Issues

### Issue: Container won't start
```bash
docker logs ai_hr_backend
# Check for:
# - Port already in use
# - Memory constraints
# - Missing environment variables
```

### Issue: Performance degradation
```bash
# Check resource usage
docker stats

# Rebuild FAISS index
cd backend
python -c "from search_service import SemanticSearchService; SemanticSearchService().rebuild_index()"
```

### Issue: Database connection errors
```bash
# Verify connection string
echo $DATABASE_URL

# Test connection
python -c "from database import engine; engine.execute('SELECT 1')"
```

---

## Rollback Procedure

### Docker Deployment
```bash
# Tag previous working version
docker tag ai-hr-backend:previous ai-hr-backend:latest

# Restart with previous version
docker-compose up -d backend --force-recreate
```

### Database Rollback
```bash
# Restore from backup
psql -U {user} -d ai_hr_saas < backup_2024_01_19.sql
```

---

## Summary

Choose deployment based on your needs:
- **Local**: Development and testing
- **Docker**: Small to medium production
- **AWS ECS**: Enterprise-scale deployment
- **DigitalOcean**: Cost-effective production
- **Heroku**: Fastest deployment, managed platform
- **GCP**: Integrations with Google services

For more details, refer to the main README.md file.
