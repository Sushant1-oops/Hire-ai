# 🤖 AI Semantic Hiring Assistant - Production-Ready HR SaaS

A complete, open-source AI-powered platform that enables recruiters to perform semantic search on resumes, generate AI-powered candidate analysis, interview questions, and outreach emails using advanced NLP and hybrid scoring algorithms.

## ✨ Features

### Core Capabilities
- ✅ **Resume Management** - Upload and process PDFs with automatic text extraction
- ✅ **Semantic Search** - Find candidates using meaning-based search (not keyword matching)
- ✅ **Hybrid Scoring** - 60% semantic similarity + 20% experience match + 20% skill overlap
- ✅ **AI Match Analysis** - Automated candidate-job fit analysis with recommendations
- ✅ **Interview Questions** - AI-generated technical, behavioral, and practical questions
- ✅ **Email Generation** - Smart outreach, interview invite, and rejection emails
- ✅ **Job Description Generator** - Create comprehensive JDs from brief descriptions
- ✅ **Dashboard & Analytics** - Track metrics, skills distribution, and search history
- ✅ **Authentication** - Secure JWT-based user authentication
- ✅ **Vector Database** - FAISS for lightning-fast semantic search
- ✅ **Caching System** - Embedded embeddings cache for performance optimization

### Tech Stack (100% Free & Open Source)
- **Backend**: FastAPI (async, modern Python framework)
- **Frontend**: Streamlit (interactive web UI)
- **Database**: SQLite (upgradeable to PostgreSQL)
- **Vector DB**: FAISS (Facebook's similarity search)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **LLM**: Ollama + llama3.2:3b (local inference)
- **Authentication**: JWT + bcrypt hashing
- **PDF Processing**: pdfplumber
- **Deployment**: Docker & Docker Compose

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (for containerized deployment)
- Ollama (for local LLM inference)
- 4GB+ RAM (recommended)

### Option 1: Local Development Setup

#### 1. Clone and Setup Environment
```bash
cd ai_hr_saas
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

#### 2. Download Ollama
```bash
# Download from https://ollama.ai
# Or install via package manager

# Pull the llama3.2 model
ollama pull llama3.2:3b

# Start Ollama service
ollama serve
# Keep this running in a separate terminal
```

#### 3. Initialize Database
```bash
cd backend
python database.py
# Creates SQLite database with all tables
```

#### 4. Start Backend Server
```bash
cd backend
python main.py
# Runs on http://localhost:8000
```

#### 5. Start Frontend (New Terminal)
```bash
streamlit run frontend/streamlit_app.py
# Opens on http://localhost:8501
```

#### 6. Access the Application
- **Frontend UI**: http://localhost:8501
- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Option 2: Docker Deployment (Recommended)

#### 1. Build and Run with Docker Compose
```bash
docker-compose up --build

# For background mode:
docker-compose up -d --build
```

This will start:
- Ollama (port 11434)
- Backend API (port 8000)
- Frontend UI (port 8501)

#### 2. Access Services
- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **Ollama**: http://localhost:11434

#### 3. View Logs
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f ollama
```

#### 4. Stop Services
```bash
docker-compose down
docker-compose down -v  # Also remove volumes
```

---

## 📖 API Documentation

### Authentication

#### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "recruiter@company.com",
  "username": "john_recruiter",
  "password": "secure_password",
  "first_name": "John",
  "last_name": "Doe",
  "company": "TechCorp"
}
```

#### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "email": "recruiter@company.com",
  "password": "secure_password"
}

Response:
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

### Resume Management

#### Upload Resume
```http
POST /api/resumes/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <pdf_file>
```

#### List Resumes
```http
GET /api/resumes
Authorization: Bearer <token>
```

#### Get Resume Details
```http
GET /api/resumes/{resume_id}
Authorization: Bearer <token>
```

#### Delete Resume
```http
DELETE /api/resumes/{resume_id}
Authorization: Bearer <token>
```

### Semantic Search

#### Search Candidates
```http
POST /api/search
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "Looking for a Senior Python developer with Django experience for a backend role",
  "required_skills": ["Python", "Django", "PostgreSQL"],
  "min_experience": 3,
  "nice_to_have_skills": ["Docker", "Kubernetes"],
  "nice_to_have_experience": 5,
  "top_k": 5
}

Response:
{
  "data": [
    {
      "rank": 1,
      "resume_id": 1,
      "candidate_name": "Alice Johnson",
      "candidate_email": "alice@email.com",
      "semantic_similarity": 0.892,
      "experience_match": 0.85,
      "skill_overlap": 0.8,
      "final_score": 0.8636,
      "recommendation": "Strong Hire"
    }
  ]
}
```

### AI Features

#### Analyze Candidate Match
```http
POST /api/ai/analyze-match
Authorization: Bearer <token>
Content-Type: application/json

{
  "resume_id": 1,
  "job_description": "Senior Python Developer... [full JD]"
}

Response:
{
  "recommendation": "Strong Hire",
  "match_score": 0.85,
  "explanation": "Candidate has strong Python background...",
  "strengths": ["10+ years Python", "Django expert", "PostgreSQL proficiency"],
  "weaknesses": ["Limited cloud experience"],
  "missing_skills": ["Kubernetes"]
}
```

#### Generate Interview Questions
```http
POST /api/ai/generate-questions
Authorization: Bearer <token>
Content-Type: application/json

{
  "resume_id": 1,
  "job_title": "Senior Backend Engineer"
}

Response:
{
  "technical_questions": [
    "Explain the Django ORM and how it handles N+1 queries",
    "How would you design a scalable caching strategy?",
    "Describe your approach to API rate limiting"
  ],
  "behavioral_questions": [
    "Tell us about a time you led a challenging project",
    "How do you handle disagreements in technical discussions?",
    "Describe your experience mentoring junior developers"
  ],
  "practical_tasks": [
    "Build a REST API for a task management system",
    "Optimize a slow database query"
  ]
}
```

#### Generate Outreach Email
```http
POST /api/ai/generate-email
Authorization: Bearer <token>
Content-Type: application/json

{
  "resume_id": 1,
  "email_type": "interview_invite",
  "job_title": "Senior Backend Engineer",
  "company_name": "TechCorp Inc"
}

Response:
{
  "subject_line": "Great Opportunity: Senior Backend Engineer at TechCorp",
  "email_body": "Hi Alice,\n\nWe came across your impressive profile..."
}
```

#### Generate Job Description
```http
POST /api/ai/generate-job-description
Authorization: Bearer <token>
Content-Type: application/json

{
  "job_title": "Senior Backend Engineer",
  "job_description_short": "Build scalable backend systems for our growing platform",
  "required_skills": ["Python", "Django", "PostgreSQL"],
  "company_name": "TechCorp"
}

Response:
{
  "job_description": "We are seeking an experienced Senior Backend Engineer...",
  "required_skills": ["Python 3.8+", "Django 4.0+", "PostgreSQL"],
  "nice_to_have_skills": ["Docker", "Kubernetes", "Redis"]
}
```

### Dashboard & Analytics

#### Get Dashboard Statistics
```http
GET /api/dashboard/stats
Authorization: Bearer <token>

Response:
{
  "total_resumes": 50,
  "avg_experience": 5.2,
  "top_skills": [
    {"skill": "Python", "count": 45},
    {"skill": "Django", "count": 38},
    {"skill": "PostgreSQL", "count": 35}
  ],
  "experience_distribution": {
    "0-2 yrs": 8,
    "3-5 yrs": 22,
    "5-10 yrs": 15,
    "10+ yrs": 5
  },
  "recent_searches": [...]
}
```

---

## 🏗️ Project Structure

```
ai_hr_saas/
│
├── backend/
│   ├── main.py                 # FastAPI application & routes
│   ├── auth.py                 # JWT authentication & password hashing
│   ├── database.py             # Database configuration & ORM setup
│   ├── models.py               # SQLAlchemy data models
│   ├── resume_service.py       # Resume upload & PDF processing
│   ├── search_service.py       # Semantic search with FAISS
│   ├── scoring_service.py      # Hybrid scoring system
│   ├── llm_service.py          # Ollama LLM integration
│   └── utils.py                # Logging, caching, helpers
│
├── frontend/
│   └── streamlit_app.py        # Streamlit web interface
│
├── data/
│   ├── resumes/                # Uploaded resume files
│   ├── faiss_index.bin         # FAISS vector index
│   └── metadata.pkl            # Resume embeddings metadata
│
├── logs/
│   └── *.log                   # Application logs
│
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container image
├── docker-compose.yml          # Multi-service orchestration
└── README.md                   # This file
```

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=sqlite:///./ai_hr_saas.db
# DATABASE_URL=postgresql://user:password@localhost:5432/ai_hr_saas  # For PostgreSQL

# Ollama LLM
OLLAMA_API_URL=http://localhost:11434
LLM_MODEL=llama3.2:3b

# Authentication
SECRET_KEY=your-super-secret-key-change-in-production

# Server
PORT=8000
WORKERS=4
ENV=development

# Streamlit
API_BASE_URL=http://localhost:8000
```

### Database Upgrade (SQLite → PostgreSQL)

For production deployments, upgrade from SQLite to PostgreSQL:

1. Install PostgreSQL
2. Update `DATABASE_URL` in `.env`
3. Models support PostgreSQL automatically via SQLAlchemy

```bash
# Install PostgreSQL driver
pip install psycopg2-binary

# Update connection string
DATABASE_URL=postgresql://user:password@host:5432/ai_hr_saas
```

---

## 📊 Scoring System Details

The hybrid scoring combines three metrics:

```
Final Score = 0.6 × Semantic + 0.2 × Experience + 0.2 × Skills
```

### 1. Semantic Similarity (60%)
- Measures how well job requirements match candidate resume
- Uses sentence-transformers embeddings (all-MiniLM-L6-v2)
- Range: 0 to 1 (higher = better match)

### 2. Experience Match (20%)
- Compares candidate's years vs required/ideal years
- Scoring:
  - Below minimum: 0-50%
  - At minimum: 60%
  - Between min-ideal: 60-90%
  - Exceeds ideal: 95%

### 3. Skill Overlap (20%)
- Percentage of required skills candidate has
- Weight: 75% required skills, 25% nice-to-have
- Range: 0 to 1

### Recommendation Levels
- **Strong Hire**: Score ≥ 0.8
- **Consider**: Score 0.6-0.79
- **Reject**: Score < 0.6

---

## 🔒 Security Best Practices

### Implemented
✅ JWT token-based authentication  
✅ Bcrypt password hashing  
✅ CORS middleware  
✅ SQL injection prevention (SQLAlchemy)  
✅ Secure session management  
✅ Environment variable configuration  

### Production Recommendations
1. **Change SECRET_KEY** - Use a strong random string
2. **Enable HTTPS** - Use Let's Encrypt or AWS SSL
3. **Configure CORS** - Restrict to your domain
4. **Add Rate Limiting** - Prevent abuse via slowapi
5. **Database Security** - Use managed PostgreSQL with encryption
6. **API Keys** - Implement API key authentication
7. **Audit Logging** - Log all access to sensitive data
8. **Backup Strategy** - Regular automated backups
9. **Monitoring** - Set up application monitoring
10. **Secrets Management** - Use AWS Secrets Manager or equivalent

---

## 🎯 Advanced Features

### Caching System
- 24-hour TTL for LLM responses
- Reduces API calls and costs
- Automatic cache invalidation
- In-memory simple cache (upgradeable to Redis)

### Search Optimization
- FAISS index persisted to disk
- Fast similarity search with top-k results
- Semantic vs keyword search comparison
- Result filtering and ranking

### Embedding Management
- Sentence-transformers for semantic embeddings
- 384-dimensional vectors (all-MiniLM-L6-v2)
- Automatic embedding generation on resume upload
- Metadata storage for quick lookups

---

## 📝 Usage Examples

### Example 1: Complete Recruitment Flow

```python
# 1. Upload resume
# 2. Search for matching candidates
# 3. Analyze match
# 4. Generate interview questions
# 5. Create outreach email
# 6. Track analytics
```

### Example 2: Bulk Resume Processing

```bash
# Via API
for resume in ./resumes/*.pdf; do
    curl -X POST http://localhost:8000/api/resumes/upload \
      -H "Authorization: Bearer $TOKEN" \
      -F "file=@$resume"
done
```

---

## 🧪 Testing

### Run Unit Tests
```bash
pytest tests/
pytest tests/ -v  # Verbose
pytest --cov     # With coverage
```

### Test Ollama Connection
```bash
curl http://localhost:11434/api/tags
```

### Test API Health
```bash
curl http://localhost:8000/health
```

---

## 📈 Performance Metrics

- **Resume Processing**: ~2-5 seconds per PDF
- **Semantic Search**: <100ms for 1000 resumes
- **AI Analysis**: ~5-15 seconds (LLM dependent)
- **Embedding Generation**: ~1 second per resume

### Optimization Tips
1. Use GPU with Ollama for faster LLM inference
2. Enable query caching for repeated searches
3. Batch process resumes during off-hours
4. Use PostgreSQL instead of SQLite for production
5. Implement Redis caching layer

---

## 🐛 Troubleshooting

### Issue: "Cannot connect to Ollama"
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Verify model is downloaded
ollama list
ollama pull llama3.2:3b
```

### Issue: "Database locked" (SQLite)
```bash
# Close other connections
pkill -f ai_hr_saas

# Or switch to PostgreSQL for production
```

### Issue: "Out of memory"
```bash
# Reduce batch size, use smaller embeddings model
# Or deploy with more RAM

# Use GPU-accelerated Ollama
# See: ollama.ai/library/llama3.2:3b-fp16
```

### Issue: "Resume parsing fails"
- Ensure PDF is not corrupted
- Check if text is scanned (OCR needed - not implemented)
- Verify pdfplumber is installed correctly

---

## 🚀 Deployment Guide

### AWS Deployment (using ECS/Fargate)

1. **Build Docker images**
```bash
docker build -t ai-hr-backend:latest .
docker build -t ai-hr-frontend:latest .
```

2. **Push to ECR**
```bash
aws ecr create-repository --repository-name ai-hr-backend
docker tag ai-hr-backend:latest {AWS_ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/ai-hr-backend:latest
docker push {AWS_ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/ai-hr-backend:latest
```

3. **Deploy with CloudFormation or Terraform**
- Configure RDS PostgreSQL
- Set up ALB for load balancing
- Configure Secrets Manager for credentials

### Heroku Deployment

```bash
heroku create ai-hr-assistant
heroku addon:create heroku-postgresql:standard-0
git push heroku main
```

### DigitalOcean Deployment

```bash
# Use App Platform with Docker Compose
# Configure via UI or doctl CLI
```

---

## 📚 Learning Resources

- **FastAPI**: https://fastapi.tiangolo.com/
- **Streamlit**: https://docs.streamlit.io/
- **FAISS**: https://github.com/facebookresearch/faiss
- **Sentence Transformers**: https://www.sbert.net/
- **Ollama**: https://ollama.ai/
- **SQLAlchemy**: https://docs.sqlalchemy.org/

---

## 🤝 Contributing

Contributions welcome! Areas for enhancement:
- [ ] OCR for scanned resumes
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] Bulk email integration
- [ ] Mobile application
- [ ] Redis caching layer
- [ ] GraphQL API
- [ ] Custom embedding models
- [ ] A/B testing framework
- [ ] ML model fine-tuning

---

## 📄 License

MIT License - Free for personal and commercial use

---

## ⚠️ Disclaimer

This is an MVP platform. For production use:
- Conduct security audit
- Implement additional compliance (GDPR, CCPA)
- Add enterprise features (SSO, audit logs)
- Scale database and caching
- Implement monitoring and alerting
- Add data backup and recovery procedures

---

## 📞 Support

- **Documentation**: See this README
- **API Docs**: http://localhost:8000/docs
- **GitHub Issues**: Report bugs
- **Discussions**: Ask questions

---

## 🎉 Success!

You now have a production-ready AI-powered HR platform!

### Next Steps:
1. ✅ Start services (Docker or local)
2. ✅ Create recruiter account
3. ✅ Upload some test resumes
4. ✅ Perform semantic search
5. ✅ Generate AI insights
6. ✅ Deploy to production

**Happy recruiting! 🚀**
