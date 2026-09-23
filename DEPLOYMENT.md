# Deployment

## Docker Compose (single host)
`docker compose up --build`. Order is enforced: Postgres healthy → `migrate` (alembic) → API and worker. Set in `.env`: `SECRET_KEY`, `POSTGRES_PASSWORD`, `ALLOWED_ORIGINS`, `CLOUDINARY_URL`, `GROQ_API_KEY`. Put a TLS-terminating proxy in front and set `TRUST_PROXY=true` so rate limits see real client IPs.

## Kubernetes
```bash
kubectl apply -f k8s/namespace.yaml
kubectl -n hireai create secret generic hireai-secrets ...     # see k8s/secret.example.yaml
kubectl apply -k k8s/                                          # config, Postgres, Redis, API, worker, HPA, ingress
kubectl apply -f k8s/migrate-job.yaml                          # run once per release, before rolling the API
```
- Build and push the backend image, then replace `hireai-backend:latest` in `api.yaml`, `worker.yaml`, `migrate-job.yaml`.
- Resumes must be in Cloudinary (the ConfigMap sets `STORAGE_BACKEND=cloudinary`); pods do not share a disk.
- Probes: `/health/live` (startup, liveness), `/health/ready` (readiness, checks the database and Redis).
- The in-cluster Postgres is a demo. For real data use a managed PostgreSQL with pgvector and point `DATABASE_URL` at it.
- The worker HPA scales on CPU. Scaling on queue depth needs KEDA.
- Redis here has no persistence: if it restarts, queued jobs are lost. Rows stay `pending`; recover with `POST /api/resumes/reprocess-pending`.

## Production checklist
- `APP_ENV=production` (the app refuses weak `SECRET_KEY`, wildcard CORS)
- `LOG_FORMAT=json`, ship stdout to your log platform
- `LANGSMITH_API_KEY` for LLM traces (optional)
- Back up PostgreSQL; embeddings can be rebuilt (`/api/resumes/reindex`), the resume text and metadata cannot
- Decide a retention period for resumes and `audit_logs`; neither is pruned automatically
