---
title: HireAI Backend
emoji: 🤖
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
---
# HireAI

Multi-tenant recruiting platform. HR users upload resumes or share a public apply link; HireAI parses each resume, ranks candidates against a job, and uses an LLM to explain, not decide.

```
React (TanStack) ──► FastAPI ──► PostgreSQL + pgvector   users, jobs, resumes, chunks, audit
                        │  └───► Redis                   cache, rate limits, job queue
                        │  └───► Cloudinary              resume PDFs (private, API-proxied)
                        ▼
                  Redis queue ──► Worker: PDF/OCR → extraction → MiniLM chunks → pgvector

search:  tenant + metadata filter → pgvector top 50 → cross-encoder rerank → 40/40/20 hybrid score
LLM:     explains the engine's result, drafts questions/emails/JDs. Output is schema- and business-validated.
```

What was fixed in the latest audit, and what is still open: [docs/CHANGES.md](docs/CHANGES.md).

## Run it

**Docker (Postgres, Redis, migration, API, worker, frontend)**
```bash
cp backend/.env.example .env      # set SECRET_KEY, GROQ_API_KEY, CLOUDINARY_URL
docker compose up --build         # API :8000, frontend :3000
```
Without `CLOUDINARY_URL` resumes go to a local volume. Without `GROQ_API_KEY` the LLM features need Ollama: `docker compose --profile ollama up`.

**Local dev (PostgreSQL + pgvector)**
```bash
cd backend
cp .env.example .env                  # set DATABASE_URL, SECRET_KEY, etc.
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload

cd ../Frontend && cp .env.example .env && npm install && npm run dev
```

## Cloudinary
1. Create a Cloudinary account, copy the API environment variable from the console (`cloudinary://<key>:<secret>@<cloud>`), and set it as `CLOUDINARY_URL`.
2. Resumes upload as `raw` assets with delivery type `authenticated`. The browser never gets a Cloudinary URL: `GET /api/resumes/{id}/file` checks the tenant and streams the PDF.
3. If downloads fail with 401/403 on a new account, check Cloudinary's Security settings for restrictions on PDF/ZIP delivery.
4. Free plans cap raw file size (10 MB at the time of writing); `MAX_UPLOAD_MB` defaults to 10.

## Moving from the old FAISS version
Vectors are derived data. Start the new version, log in, and call `POST /api/resumes/reindex` (or the "Rebuild index" button). Old `data/faiss_index.bin` and the pickle are no longer read and can be deleted.

## Test and evaluate
```bash
cd backend
python -m unittest discover -s tests -t .        # unit tests; API tests run when web deps are installed
python -m evaluation.run_extraction               # field extraction on a labelled set
python -m evaluation.run_retrieval                # bi-encoder vs +rerank vs hybrid (needs the models)
```
The bundled datasets are tiny synthetic smoke tests. They prove the harness runs; they do not measure quality. Label real resumes before quoting any number.

## Layout
Every module lives in the folder for what kind of thing it is — one canonical copy of each file, nothing duplicated at the backend root.

```
backend/
  main.py                app, middleware, error handling (the only loose file — the ASGI entrypoint uvicorn points at)

  routers/                HTTP layer: request/response only, no business logic
    auth_routes.py  resume_routes.py  job_routes.py  search_routes.py  ai_routes.py  system_routes.py

  core/                   cross-cutting infrastructure everything else depends on
    config.py  database.py  security.py  rate_limit.py  audit.py  observability.py  utils.py

  auth/                   authentication
    auth.py (tokens, hashing, register/login)  deps.py (FastAPI auth dependencies)

  models/                 SQLAlchemy models (tenant = HR account = users.id)
    models.py

  ai/                     resume/text/ML processing — no DB or HTTP concerns
    extraction.py (OCR, name+confidence, phone, experience intervals, education)
    skills_extractor.py  chunking.py  vector_store.py  reranker.py  llm_safety.py

  services/               business logic and orchestration — talks to core/auth/ai/models
    embedding_service.py  search_service.py  scoring_service.py  resume_service.py
    job_service.py  pipeline_service.py  llm_service.py  storage_service.py
    cache_service.py  queue_service.py

  workers/                background job processing (separate process from the API)
    tasks.py (job bodies)  worker.py (RQ entrypoint — run with `python -m workers.worker`)

  migrations/             Alembic
  evaluation/             extraction/retrieval/LLM quality harnesses + datasets/
  tests/                  unit tests, mirroring the folders above
  scripts/                one-off ops scripts, not imported by the app (e.g. verify_pgvector.py)

Frontend/                 TanStack Start app
```
