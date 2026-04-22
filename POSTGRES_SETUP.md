# PostgreSQL Database Setup Guide

This guide helps you set up PostgreSQL for the AI HR Assistant project.

## Prerequisites

### Windows Installation

1. **Download PostgreSQL**
   - Go to: https://www.postgresql.org/download/windows/
   - Download the latest version (PostgreSQL 16.x recommended)
   - Run the installer

2. **During Installation**
   - Set a secure password for the `postgres` superuser
   - Default port is `5432`
   - Remember the password as you'll need it

3. **Verify Installation**
   ```powershell
   psql --version
   ```

## Database Setup

### 1. Create Database and User

```sql
-- Connect as postgres user
psql -U postgres

-- Create database
CREATE DATABASE hr_assistant;

-- Create application user
CREATE USER hr_user WITH PASSWORD 'your_secure_password';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE hr_assistant TO hr_user;

-- Connect to the database
\c hr_assistant

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO hr_user;

-- Exit
\q
```

### 2. Environment Variables

Create a `.env` file in the project root:

```env
# Database Configuration
DATABASE_URL=postgresql://hr_user:your_secure_password@localhost:5432/hr_assistant

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# JWT Secrets
SECRET_KEY=your-super-secret-key-change-in-production
ALGORITHM=HS256

# Ollama Configuration (for AI features)
OLLAMA_BASE_URL=http://localhost:11434

# Frontend Configuration
FRONTEND_URL=http://localhost:5173

# Redis (optional, for caching)
# REDIS_URL=redis://localhost:6379/0
```

### 3. Backend Database Models

The following tables will be created automatically:

- **users** - User accounts and authentication
- **resumes** - Uploaded resumes
- **candidates** - Extracted candidate information
- **search_history** - User search records
- **search_results** - Semantic search results
- **ai_candidate_matches** - AI matching scores
- **interview_questions** - Generated interview questions
- **outreach_emails** - Generated email templates
- **job_descriptions** - Job description records

### 4. Run Database Migrations

```powershell
# From the project root
cd backend

# Activate Python environment (if using venv)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from database import init_db; init_db()"

# Or run the backend which will auto-create tables
python main.py
```

## Common PostgreSQL Commands

```powershell
# Connect to database
psql -U hr_user -d hr_assistant -h localhost

# List databases
\l

# List tables
\dt

# Describe table
\d table_name

# Query data
SELECT * FROM users;

# Backup database
pg_dump -U hr_user -d hr_assistant > backup.sql

# Restore database
psql -U hr_user -d hr_assistant < backup.sql
```

## Connection String Format

```
postgresql://[user]:[password]@[host]:[port]/[database]

Example:
postgresql://hr_user:password123@localhost:5432/hr_assistant
```

## Troubleshooting

### Connection Refused
- Check if PostgreSQL service is running: `tasklist | findstr postgres`
- Start PostgreSQL service on Windows
- Check port 5432 is not blocked

### Authentication Failed
- Verify password is correct
- Check username exists: `psql -U postgres -l`
- Ensure user has database privileges

### Database Already Exists
- Drop existing: `DROP DATABASE hr_assistant;`
- Then recreate as shown above

## Performance Tips

1. **Indexing**
   ```sql
   -- Add indexes for common searches
   CREATE INDEX idx_candidates_email ON candidates(email);
   CREATE INDEX idx_candidates_skills ON candidates(skills);
   CREATE INDEX idx_resumes_user_id ON resumes(user_id);
   ```

2. **Connection Pooling**
   - Production: Use PgBouncer or similar
   - Connection string: Add `?sslmode=require` for SSL

3. **Maintenance**
   ```sql
   -- Analyze table for query optimization
   ANALYZE candidates;
   VACUUM ANALYZE;
   ```

## Docker Alternative (Optional)

Instead of installing PostgreSQL locally, you can use Docker:

```powershell
# Download image
docker pull postgres:16-alpine

# Run container
docker run -d `
  --name pg_hr_assistant `
  -e POSTGRES_USER=hr_user `
  -e POSTGRES_PASSWORD=your_password `
  -e POSTGRES_DB=hr_assistant `
  -p 5432:5432 `
  -v pg_data:/var/lib/postgresql/data `
  postgres:16-alpine

# Connect
docker exec -it pg_hr_assistant psql -U hr_user -d hr_assistant

# Stop container
docker stop pg_hr_assistant

# Remove container
docker rm pg_hr_assistant
```

## Data Migration

If migrating from another database:

```bash
# Export from old system
pg_dump -U old_user -d old_db > export.sql

# Import to new database
psql -U hr_user -d hr_assistant < export.sql
```

## Security Best Practices

1. **Use strong passwords** - At least 12 characters with mixed case, numbers, symbols
2. **Limit user privileges** - Don't use superuser for application
3. **Enable SSL** - In production, use SSL connections
4. **Regular backups** - Daily automated backups recommended
5. **Monitor access** - Log all database access attempts

## Next Steps

1. Set up PostgreSQL following steps above
2. Create `.env` file with database credentials
3. Run backend: `python backend/main.py`
4. Run frontend: `npm run dev` (from frontend directory)
5. Access at: `http://localhost:5173`

## Support

For PostgreSQL help:
- Official Docs: https://www.postgresql.org/docs/
- Community: https://www.postgresql.org/community/
