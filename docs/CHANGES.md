# Audit & fixes

## Security
- **Resume overwrite via the public form (fixed).** Anyone could apply with another candidate's email and replace that candidate's stored resume and name. A different PDF now always creates a *new* resume; the same PDF reuses the existing one. If the job already has an application from that email it is re-pointed to the new resume.
- **Live secrets shipped in the archive.** The uploaded zip contained a `.env` with a real Groq key and SMTP password. It is not in this package. **Rotate both.** `.gitignore` now covers `.env.*`.
- `.gitignore` ignored `tests/` (the suite was never committed) and an unanchored `lib/` (matched `Frontend/src/lib`). Both fixed.
- Logout now revokes the refresh token server-side.

## Scoring
- Semantic similarity is **calibrated** (`SEMANTIC_FLOOR`/`SEMANTIC_CEIL`). Raw MiniLM cosine rarely exceeds ~0.6, so its 40% weight could never be fully earned and every score was compressed. Ranking order is unchanged; absolute scores and the recommendation bands are now meaningful. *These two values are starting points — tune them with `evaluation/run_retrieval.py` on your own labelled resumes.*
- Required skills outside the taxonomy ("Negotiation", "Tally ERP") were silently dropped, so non-technical jobs scored on nothing. They are now kept and matched against the resume text.
- Matched/missing skill lists are in the job's order (they were set-ordered and changed between requests).
- **One scoring path.** The job applicant list, the worker, and AI Hub's *Analyze match* all use `score_payload`, so a candidate has one score per job. AI Hub previously ignored the job's minimum experience and skills.
- Scores are **stored** on the application (`score_details`) when a resume finishes processing or a job changes. Opening an applicant list no longer re-embeds and cross-encodes every candidate on every view (the old 30 s cache is gone — nothing to invalidate).
- The pasted job description in Search was ignored for the semantic query; it is now used.

## Extraction
- spaCy model was reloaded for every resume (~1 s each); now cached.
- Only the first experience section was read; all are summed ("Work Experience" + "Internships").
- Emails glued to following text by PDF extraction (`a@b.comLinkedIn`) are trimmed.
- Degrees are read from the Education section only. `Go` is detected in list position. PDFs are capped at `MAX_PDF_PAGES`.

## Jobs
- Added: edit job, delete job, close/reopen in the UI, add a library candidate to a job, remove an applicant, detect skills from a description.
- Required skills are canonicalised (`postgres` → `PostgreSQL`) and auto-detected from the description when none are given.

## AI
- "Regenerate" returned the identical cached text; creative output (emails, questions, JDs) is no longer cached.
- JD generation: dict/list model output no longer rendered as a Python repr; markdown stripped (the apply page shows plain text); the model is told not to invent salary/perks; skills canonicalised; suggests minimum experience; company defaults to the user's company.
- Email sending now reports real SMTP success/failure (it used to say "queued" and log failures), and marks the drafted email as sent.

## Resilience / latency
- Redis enqueue failure no longer 500s an upload (falls back to in-process).
- A scoring error after a successful parse no longer marks the resume "failed".
- Resume list and search no longer load every resume's full text.

## Dashboard
Removed top skills, experience distribution, average experience, recent searches. Now: awaiting-decision / in-progress / hired counts, the best candidates not yet decided, hiring funnel, open jobs with new-applicant counts, and resume-library health (failed / needs-check / processing).

## Frontend
Resumes page polls while processing, filters, retry for failures, edit misparsed details; candidate drawer shows the jobs a candidate is in; job page has stage filters, score breakdown per applicant, job-aware AI Hub; Search gets "start from a job", strict mode, evidence snippet, add-to-job.

## Removed
Unused `analytics_dashboard` / `search_results` tables and models (migration `0002`), dead helpers in `core/utils.py`, the Lovable error shim, junk docs.

## Not verified / still open
- The DB- and HTTP-facing code (routers, SQL aggregates, Alembic `0002`) could not be executed where this audit ran (no PostgreSQL/FastAPI available). It was import-checked and name-checked; **run the app and `alembic upgrade head` once against a copy of your data**.
- The frontend was syntax- and import-checked with `tsc` but not built (no `node_modules`).
- Unit tests: 80 pass (extraction, skills, scoring, chunking, safety, security, storage).
- `Frontend/Dockerfile` serves with `vite preview`; confirm that is right for your deployment target.
- `init_db()` still alters tables at startup alongside Alembic; prefer Alembic only in production.
