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

Why it is built this way: [docs/ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md). What changed and what is still open: [docs/V2_GAP_AUDIT.md](docs/V2_GAP_AUDIT.md).

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
```
backend/
  main.py              app, middleware, error handling
  routers/             auth, resumes, jobs (+public apply), search, ai, system
  models.py            SQLAlchemy models (tenant = HR account = users.id)
  migrations/          Alembic
  extraction.py        text/OCR, name+confidence, phone, experience intervals, education
  chunking.py  embedding_service.py  vector_store.py  reranker.py  search_service.py  scoring_service.py
  llm_service.py  llm_safety.py    LLM calls, retries, redaction, injection defence, validation
  storage_service.py   Cloudinary + local
  queue_service.py  tasks.py  worker.py
  auth.py  deps.py  rate_limit.py  audit.py  security.py
  evaluation/  tests/
k8s/                   manifests (API, worker, Redis, Postgres, HPA, probes, migration job)
Frontend/              TanStack Start app
```
