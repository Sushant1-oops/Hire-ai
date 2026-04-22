# Quick Start Commands

## 🎯 Run Everything

### Terminal 1: Frontend
```powershell
cd frontend
npm install react-feather
npm run dev
# Runs on http://localhost:5173
```

### Terminal 2: Backend  
```powershell
cd backend
# Activate your Python environment first
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
# Runs on http://localhost:8000
```

### Terminal 3: Database (PowerShell)
```powershell
# Check PostgreSQL is running
Get-Process postgres

# Or start it manually if needed
pg_ctl -D "C:\Program Files\PostgreSQL\16\data" start
```

## ✅ Verify Everything Works

```powershell
# Check frontend builds
cd frontend
npm run build

# Check backend
cd ../backend
python -c "import main; print('Backend OK')"

# Check database
psql -U hr_user -d hr_assistant -c "SELECT 1"
```

## 🌐 Access Points

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432

## 📊 Login Credentials (Demo)

- Email: `demo@example.com`
- Password: `demo123`

Or register a new account

## 🛠️ Development Commands

### Frontend
```powershell
npm run dev      # Start dev server
npm run build    # Production build
npm run preview  # Preview production build
npm run lint     # Check code
```

### Backend
```powershell
python main.py                  # Run server
# Or with auto-reload for development:
uvicorn main:app --reload
```

## 📝 Environment Setup

1. Create `.env` in project root:
```
DATABASE_URL=postgresql://hr_user:password@localhost:5432/hr_assistant
API_HOST=0.0.0.0
API_PORT=8000
SECRET_KEY=your-secret-key-here
```

2. Create `frontend/.env.local`:
```
VITE_API_URL=http://localhost:8000/api
```

## 🗄️ Database Commands

```powershell
# Connect to database
psql -U hr_user -d hr_assistant

# List all tables
\dt

# View users table
SELECT * FROM users;

# View resumes table
SELECT * FROM resumes;

# Exit
\q
```

## 🚀 Production Build

```powershell
# Build frontend
cd frontend
npm run build
# Output: frontend/dist/

# Backend with gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

## 🐛 Debug Mode

### Frontend
```powershell
# Dev tools already enabled
# Check browser console: F12 or right-click > Inspect
```

### Backend
```powershell
# Add to main.py before run:
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")
```

## ⚡ Performance Check

```powershell
# Frontend build size
cd frontend
ls -l dist/assets/

# Backend response time
# Check backend logs for API response times
```

## 📦 Dependencies Installed

### Frontend
- react@19.2.0
- vite@7.3.1
- tailwindcss@4.2.1
- @tailwindcss/vite@4.2.1
- react-feather (icons)

### Backend
- fastapi
- sqlalchemy
- psycopg2-binary
- pydantic
- python-jose
- passlib

## 🎯 Common Issues & Fixes

**Frontend port in use:**
```powershell
npm run dev -- --port 3000
```

**Backend port in use:**
```powershell
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**PostgreSQL not running:**
```powershell
# Windows Services
Get-Service PostgreSQL* | Start-Service

# Or direct command
pg_ctl -D "C:\Program Files\PostgreSQL\16\data" start
```

**Dependencies missing:**
```powershell
# Frontend
npm install

# Backend
pip install -r requirements.txt
```

## 📞 Support

Refer to:
- `FRONTEND_README.md` - Frontend docs
- `POSTGRES_SETUP.md` - Database setup
- `backend/MODELS_DOCUMENTATION.md` - Backend models

Enjoy your HR Assistant! 🎉
