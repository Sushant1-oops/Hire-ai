from backend.database import get_db
from backend.models import Resume

with get_db() as db:
    resumes = db.query(Resume).all()
    for r in resumes:
        print('ID', r.id, 'name', r.candidate_name, 'email', r.candidate_email, 'skills', r.skills)
