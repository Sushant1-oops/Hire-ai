# What was fixed

## The root cause of "everything is broken"
The backend wraps every response in an envelope: `{ error, message, data, timestamp }`.
The frontend's API client was reading the raw JSON body as if that envelope didn't
exist, so every field it read off a response was `undefined` — including
`tokens.access_token` on login. That's why auth, the dashboard, resumes, search and
the AI Hub all looked broken at once: they all go through the same client.

Fixed in `Frontend/src/lib/api.ts`: `apiRequest` now unwraps `data` automatically and
surfaces the backend's actual error `message` (or FastAPI's own validation error) as
the thrown error.

## Backend bugs
- **Dashboard was crashing on every load.** `/api/dashboard/stats` called
  `ResumeService.get_resume_statistics(...)`, a method that did not exist anywhere in
  the codebase. Added it (`backend/resume_service.py`) — total resumes, average
  experience, top skills, experience-band distribution.
- **Experience scoring was always wrong.** `ScoringService.score_candidate` hard-coded
  `candidate_experience=None`, so a candidate's real parsed experience never affected
  their experience-match score. Fixed to pass the real value through from
  `search_service.py`.
- **Cross-tenant data leak.** Semantic search queried the shared FAISS index without
  filtering by `user_id`, so one recruiter's search could return another user's
  uploaded resumes. `SearchService.search` / `search_with_scoring` now scope results
  to the requesting user.
- **No server-side password validation** — only enforced client-side, so the API
  itself would accept a 1-character password. Added a minimum-length validator.
- **CORS** was `allow_origins=["*"]` combined with `allow_credentials=True`, which is
  invalid per the CORS spec. Now configurable via `ALLOWED_ORIGINS` and credentials
  are only enabled when origins are explicitly restricted.
- **Docker build was broken.** The Dockerfile copied `requirements.txt` from the
  repo root, but that file only exists at `backend/requirements.txt` — `docker build`
  failed immediately. Fixed the path.
- **docker-compose was broken in two ways:** the backend's `command:` ran
  `python backend/main.py` from a working directory that is already `backend/`,
  looking for a `backend/backend/main.py` that doesn't exist; and the `frontend`
  service ran `streamlit run frontend/streamlit_app.py` — a leftover from an earlier
  Streamlit version of this project. Neither file exists in this codebase (the actual
  frontend is the TanStack Start app in `Frontend/`). Rewrote `docker-compose.yml`
  and added a real `Frontend/Dockerfile`.

## Frontend bugs
- **Field-name mismatches across almost every screen.** The backend returns
  `candidate_name` / `candidate_email` / `candidate_phone` / `experience_years`; the
  frontend types expected `name` / `email` / `phone` / `years_of_experience`. Fixed
  consistently in `lib/types.ts` and everywhere those fields are read (resumes list,
  search results, candidate drawer).
- **AI Hub was non-functional.** All four actions called the backend with the wrong
  payload shape:
  - *Match analysis* sent `query`; the backend requires `job_description`.
  - *Interview questions* and *outreach email* never sent `job_title`, a required
    field — every call would 422.
  - *Job description generator* sent `{ summary, title }`; the backend expects
    `{ job_title, job_shorthand }`.
  - Response fields were also mismatched (`technical`/`subject`/`body` vs. what the
    backend actually returns: `technical_questions`/`subject_line`/`email_body`).
  Rewrote the component to collect a job title/description and use the real
  contracts.
- **Candidate drawer rendered education as `[object Object]`** — education entries
  are `{ degree }` objects, not strings.
- **Resumes page grouped candidates by "company"** — a field that doesn't exist on
  resumes at all, so every candidate landed in one meaningless "My company" bucket.
  Removed the grouping.
- **Dashboard read `average_experience`**; the backend returns `avg_experience`, so
  that stat card always showed 0.0 yrs. Also removed a duplicate chart ("Skill
  coverage") that showed the same data as "Top skills" a second time.
- **Register page called `login()` again right after registration**, even though
  registration already returns valid tokens — redundant and could mask a real
  registration error behind a swallowed login failure.

## Housekeeping
- Removed committed `__pycache__`, `.pyc`, log files, and a committed SQLite DB /
  FAISS index from the repo (these regenerate at runtime and are already listed in
  `.gitignore`, just hadn't been cleaned before this was zipped).
- Added `backend/.env.example` and `Frontend/.env.example`.
- `node_modules`, `.git`, and editor caches (`.tanstack`, `.lovable`) are excluded
  from this delivery — run `npm install` in `Frontend/` to restore dependencies.

## Verified
- `npx tsc --noEmit` passes with zero errors on the full frontend.
- ESLint passes on every file that was changed (remaining lint noise elsewhere in
  the repo is pre-existing CRLF line-ending style, not a functional issue).
- All touched backend files pass a Python AST syntax check.

## Setup
```bash
# Backend
cd backend
cp .env.example .env   # fill in SECRET_KEY at minimum
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd Frontend
cp .env.example .env
npm install
npm run dev
```
Or `docker compose up --build` from the repo root.

---

# New feature: job postings + public application pipeline

This adds the intake pipeline: HR creates a job → HireAI generates a public,
account-free `/apply/{slug}` link → a candidate's resume goes straight into
the existing parsing/embedding/scoring pipeline, ranked against that specific
job.

## What was added

**Backend**
- `Job` and `Application` models (`models.py`). A `Job` has a random
  `public_slug` (not the sequential id) so apply links aren't guessable by
  incrementing a number. An `Application` links one `Resume` to one `Job`,
  with a unique `(job_id, resume_id)` constraint — a candidate applying twice
  to the same job updates the existing row instead of duplicating it.
- `job_service.py` — create/list/close jobs, dedup a candidate by email
  within the HR user's own resume pool, and rank every applicant for a job
  directly against its description/skills/experience (the applicant pool for
  one job is small, so this scores directly rather than going through the
  FAISS shortlist used for open-ended search).
- Endpoints: `POST/GET /api/jobs`, `GET /api/jobs/{id}`,
  `PATCH /api/jobs/{id}/status`, `GET /api/jobs/{id}/applications`,
  `PATCH /api/applications/{id}/status`, and the public, unauthenticated
  `GET /api/public/jobs/{slug}` + `POST /api/public/jobs/{slug}/apply`.
- Removed `streamlit`/`pandas` from `backend/requirements.txt` — leftovers
  from the old Streamlit frontend; nothing in the backend imports them.
- Fixed `Job.to_dict()` and `JobDescription.to_dict()`, which were both
  returning `required_skills`/`nice_to_have_skills` as a raw JSON *string*
  instead of a parsed list — would have broken `.map()` on the frontend the
  first time the Jobs page rendered a skill badge.

**Frontend**
- `/jobs` — create a job, see application counts, copy the apply link.
- `/jobs/$jobId` — ranked applicant table with a per-candidate status
  dropdown (received → screened → shortlisted → interview → hired/rejected)
  and a "View pipeline" panel (see Observability below).
- `/apply/$slug` — the public page a candidate opens from the shared link.
  No login, no HireAI account.

## Observability & tracing

First pass at this used LangGraph to orchestrate the application-processing
steps. Per feedback, that's been removed — what's here now is plain
sequential Python plus a dedicated observability layer, which is a better
fit for "I want to monitor this" than a graph-execution framework:

**`observability.py` — two layers:**

1. **Local, always-on, zero-config.** `RunRecorder` logs every LLM call
   (match analysis, interview questions, outreach email, JD generation),
   every search, and the application pipeline to a new `observability_runs`
   table — an ordered list of steps, each with a name, status, duration, and
   error if it failed. No API key, no external service, nothing to install.
   Query it via `GET /api/observability/runs` (optionally
   `?run_type=application_pipeline`) or `GET /api/jobs/{id}/applications/{id}/pipeline`
   for one application's history. The `/monitoring` page in the frontend is
   built on this.
2. **Optional LangSmith tracing.** Set `LANGSMITH_API_KEY` (and optionally
   `LANGSMITH_PROJECT`) in `.env` and the same LLM calls are *also* traced to
   smith.langchain.com — full prompt/completion inspection, latency,
   nested-run view. `traceable()` in `observability.py` is a drop-in for
   `langsmith.traceable` that's a true no-op until a key is present, so it's
   applied unconditionally to `generate_text` and the four LLM functions in
   `llm_service.py` — nothing else needs to change to turn this on later.

`pipeline_service.py` runs the application steps in a fixed sequence (parse
→ upsert candidate → embed/index → score → create application) inside one
`RunRecorder`, rather than a graph — there's no branching here, so a graph
added a dependency without adding capability.

**What I could actually verify here, unlike the LangGraph attempt:** the
local `RunRecorder` has zero external dependencies when LangSmith isn't
configured, so I could test it directly in this sandbox with a stand-in DB —
confirmed a multi-step successful run records correctly, and confirmed a
step raising an exception marks the run `error`, records the error message,
still preserves the steps that succeeded before it, and re-raises so the
calling endpoint's own error handling still runs. That's real, run test
coverage, not just a syntax check.

**What's still unverified:** LangSmith itself. `langsmith` is in
`requirements.txt`, but this sandbox has no network to `pip install` it or
a real API key to trace against, so the *cloud* half of this was not
exercised end-to-end. It only imports at all if `LANGSMITH_API_KEY` is set,
so the app runs fine without it either way — but before relying on the
LangSmith dashboard, set a real key and confirm a run actually shows up at
smith.langchain.com.

## Explicitly not done (as agreed)
Email ingestion (a mailbox poller reading applications sent to
`jobs@company.com`) needs real IMAP/SMTP credentials and a live mailbox to
test against, which isn't available here. The `source` field on
`Application` (`form` / `email` / `manual`) is already in place so that
channel can be added later without another data-model change — it would
mean a new poller that calls the same `apply` logic (or the pipeline
directly) with `source="email"` and a job id parsed from the subject or a
`+JOB-xxxx` address, per the original proposal.

## Frontend routing note
`src/routeTree.gen.ts` is normally auto-generated by TanStack Router's Vite
plugin. This sandbox's Vite couldn't run (a broken native binding for
`rolldown`, unrelated to anything in this project — the sandbox's `npm
install` for this dependency didn't complete correctly), so I hand-wrote the
updated route tree to match what the plugin would produce for the new
`/jobs`, `/jobs/$jobId`, `/apply/$slug`, and `/monitoring` routes. Running
`npm run dev` or `npm run build` on your machine will regenerate this file
automatically and overwrite my hand-written version — that's expected and
fine.


---

# Async application processing + ranking cache

Submitting an application used to do everything synchronously inside the
HTTP request: save the file, parse the PDF, extract skills, embed into
FAISS, and score against the job — all before the candidate saw "Application
received." That's slow (embedding especially) for no reason the candidate
benefits from.

## What changed

**`pipeline_service.py` is now split in two:**
- `submit_application()` — runs in the request. Only fast I/O: an indexed
  dedup lookup by email, saving the file to permanent storage, and a row
  insert/update. The candidate's resume record is created immediately with
  `is_processed=False` — name/email/phone are already there (they typed
  them into the form), but skills/experience/extracted text aren't yet.
- `process_application_async()` — added to FastAPI's `BackgroundTasks`, so
  it runs *after* the HTTP response is already sent. Does the actual parse
  → update candidate record → embed/index → score → work, then flips
  `is_processed` to `True`. Uses its own DB session (`SessionLocal()`) since
  the request's session is closed by the time this runs.
- If the background step fails (e.g. a scanned/image-only PDF with no
  extractable text), `Resume.processing_error` is set and `is_processed`
  stays `False` — so it shows as "failed to process" rather than stuck on
  "processing" forever.

Both halves are still recorded via `RunRecorder`, so a slow or failed
background run shows up in the pipeline/monitoring views exactly like
before — the split changes *when* the work happens, not whether it's
observable.

**Frontend:** the job applications table now shows "Processing…" or "Failed
to process" instead of a score for an application still being handled in
the background, and polls every 4s while anything is pending so the score
appears on its own once ready — no manual refresh needed.

**Fixed while doing this:** temp upload filenames were `temp_apply_{filename}`
with no uniqueness — two applicants uploading a same-named `resume.pdf`
around the same time could collide. Now `temp_apply_{uuid4()}_{filename}`.
This got more important once the file has to survive past the request
(the background task needs it) instead of being deleted in the same
request's `finally` block.

## Ranking cache

`JobService.rank_applications()` re-encodes every applicant's resume text
against the job description on *every* call — real, growing CPU cost as an
applicant pool grows, and the job detail page's new polling makes repeat
calls more frequent. Added a 30-second cache (the existing `SimpleCache`
from `utils.py`, already used elsewhere for LLM response caching), but
**explicitly invalidated** — not just left to expire — whenever something
that would actually change the result happens:
- a new application arrives for that job (`create_or_update_application`)
- HR changes an application's status (`update_application_status`)
- the background pipeline finishes scoring a candidate

So a stale value can only ever be served for something that hasn't changed;
anything HR or a candidate actually does is reflected immediately regardless
of the TTL.

## What I could actually verify here
Both of these are pure-Python/SQLAlchemy logic with no external service
dependency, so — unlike LangSmith or the earlier LangGraph attempt — I could
write and run real tests against them in this sandbox (stubbing out
SQLAlchemy/models rather than installing them):
- `SimpleCache`: confirmed `.set()`/`.get()`/`.delete()` and TTL expiry all
  behave correctly.
- `JobService.rank_applications()`: confirmed a fully-processed resume gets
  scored and ranked first, a `pending` resume is skipped from scoring
  entirely (no wasted embedding calls) and shown with `processing_status:
  "pending"`, and a `failed` resume surfaces its `processing_error` — using
  fake DB/model objects rather than needing sqlalchemy installed.

What's still unverified is the actual FastAPI `BackgroundTasks` execution
and cross-thread SQLite session behavior end-to-end (needs the real
`fastapi`/`sqlalchemy` stack, which this sandbox can't install) — the logic
is straightforward and follows FastAPI's documented pattern, but run one
real application through `/apply/{slug}` and confirm the applications table
transitions from "Processing…" to a real score before relying on it.

---

# Fixes from real-world run: missing column crash + LangSmith coverage gap

## Dashboard 500: `resumes.processing_error` does not exist

Running against an existing Postgres database (created before
`processing_error` was added to `Resume`) crashed every `/api/dashboard/stats`
call with `psycopg2.errors.UndefinedColumn`. Root cause: `Base.metadata.
create_all()` only creates tables that don't exist yet — it never alters an
existing table to add a newly-declared column. This project has no Alembic,
so any column added to a model after the database already has data will hit
this exact failure.

Fixed with a lightweight auto-migration in `database.py`
(`_run_lightweight_migrations`, called from `init_db()`): after
`create_all()`, it inspects every table, compares its actual columns against
what the model declares, and issues `ALTER TABLE ... ADD COLUMN` for
anything missing, using SQLAlchemy's own `CreateColumn` compiler so the DDL
is correct for both SQLite and Postgres. This is explicitly not a real
migration system — it can only add nullable columns, never rename, drop, or
change a type. Restarting the backend should self-heal this specific error;
reach for Alembic if this project needs real migrations going forward.

## LangSmith wasn't tracing the actual pipeline, only the LLM calls

`@traceable` was applied to the 4 LLM functions (match analysis, interview
questions, outreach email, JD generation) but not to `submit_application`
or `JobService.rank_applications` — so with `LANGSMITH_API_KEY` set, the
AI Hub actions would show up on smith.langchain.com but the actual
apply → parse → embed → score → rank flow (arguably the more interesting
thing to watch) would not. Both now have `@traceable` too, alongside the
background pipeline step which already had it — the full flow is one trace
tree once a key is configured.

To be clear on what's what, since this caused confusion: the `/monitoring`
page **inside HireAI** is a separate, always-on, zero-config local log (its
own `observability_runs` table) — it has nothing to do with LangSmith and
needs no API key. LangSmith is the external dashboard at
smith.langchain.com, additive on top, and only activates when
`LANGSMITH_API_KEY` is set in `.env`.

---

# Delete resume button

The backend `DELETE /api/resumes/{id}` endpoint and `deleteResume()` in
`lib/queries.ts` already existed, but nothing in the UI ever called it —
there was no way to actually delete a resume from the app. Added:

- A delete (trash) icon on each resume card in `/resumes` (appears on
  hover, top-right corner), and a matching delete button next to "Open AI
  Recruitment Hub" in the candidate drawer.
- Both go through a confirmation dialog (can't accidentally delete) and, on
  success, invalidate the resumes list and dashboard stats so the count
  updates immediately.

---

# LangSmith-only monitoring, real email drafts, latency, and a real search-accuracy bug

## Monitoring: removed from HireAI entirely, moved fully to LangSmith

The local `/monitoring` page and its `RunRecorder`-based local run/step log
are gone. That local recorder was committing to the database multiple times
per request purely for a feature that (correctly) turned out not to be
useful to HR users — removing it is itself part of the latency fix below.

In its place: `LangSmithTracingMiddleware` (`observability.py`, wired into
`main.py`) wraps **every HTTP request** in a LangSmith trace when
`LANGSMITH_API_KEY` is set — not just the requests that happen to call an
LLM. Every `@traceable` function called while handling that request (the
LLM calls, `submit_application`, `JobService.rank_applications`) nests
underneath it automatically. With no key set, none of this runs at all —
`traceable` stays a true no-op. There is no tracing UI inside HireAI
anymore; smith.langchain.com is the only place to look.

Built the middleware carefully so a LangSmith failure can never cause a
request to be handled twice (a first draft of this had exactly that bug —
caught it before it shipped: tracing setup/teardown is now fully isolated
from the one-and-only call to the actual request handler).

## Email generation: fixed the actual placeholder cause, clarified the Send flow

Root cause: the prompt fell back to generic filler ("Our Company", "Hiring
Team", "N/A") whenever company/contact/interview details weren't supplied —
and the UI never collected them, so it always fell back. Fixed:
- The prompt now only mentions a detail if it's actually provided, and is
  explicitly told never to use bracket placeholders or "N/A"/"TBD".
- The AI Hub's email tab now collects Company and Signed-by (pre-filled
  from the logged-in HR user's own profile) and, for interview invites,
  date/time/location.
- Confirmed and clarified (this already worked, just wasn't obvious): Generate
  only drafts an editable email; clicking Send does a real SMTP send via
  `/api/email/send`, which already correctly errors out if SMTP isn't
  configured rather than pretending to succeed.

## Jobs → applications + count

This already existed (open a job, see ranked applicants and a count) — made
the whole card tappable instead of just the title text, and fixed a real
N+1 query in `GET /api/jobs`: it was calling `len(job.applications)` per
job, lazy-loading each job's full applications relationship one at a time.
Replaced with a single `GROUP BY` aggregate query for all jobs at once.

## Latency

- Removed the local tracing DB writes (above) — several synchronous commits
  per request, gone.
- Batch-encode every ready candidate's resume text in `rank_applications`
  in one call instead of one `model.encode()` call per candidate in a loop.
  Verified with a real numpy test that this produces numerically identical
  similarity scores to the old per-item approach — pure speed win, no
  behavior change.
- Fixed the `GET /api/jobs` N+1 query above.
- Fixed the deprecated `@app.on_event("startup")` → a proper `lifespan`
  context manager (FastAPI's own docs flag `on_event` for removal).
- Frontend: the `QueryClient` had `staleTime: 0` (the default), so every
  navigation back to a page refetched over the network even for data
  fetched moments earlier — every page felt like a cold load. Set to 20s,
  and cut default retries from 3 to 1 so a genuinely slow/down backend
  surfaces an error faster instead of retrying with backoff first.
- Added optimistic updates (instant UI feedback, automatic rollback on
  failure) for application status changes and resume deletion — both used
  to wait for a full round trip before the UI reflected the change.

**Being honest about the floor here:** the LLM calls (Groq/Ollama) and the
sentence-transformer embedding inference are the actual bulk of per-request
time for AI Hub actions and search, and that's inherent to calling an LLM
and running a neural network — no code change here makes an external API
call or a forward pass through a transformer faster. What's fixed above is
the *overhead this app was adding on top of that* (extra DB writes, N+1
queries, redundant per-item encode calls, unnecessary refetches) — all real
and all avoidable, but not the same thing as making Groq respond quicker.

## Semantic search accuracy: found and fixed a real, significant bug

I want to be upfront: "perfect" search isn't a real engineering target —
semantic search is inherently probabilistic. But I did find and fix a
concrete, measurable bug rather than just tuning weights and hoping.

**The bug:** the embedding model (`all-MiniLM-L6-v2`) silently truncates
any input past ~256 tokens (roughly 900-1000 characters) — text beyond
that is dropped, not summarized, and sentence-transformers doesn't warn
you this happened. The app was passing the *entire raw resume text* to the
model. A typical 1-2 page resume is well past that limit, so **whatever
happened to be in the last ~70% of a resume — often the actual skills and
experience section — never influenced its embedding at all.** Ranking and
search were, in a real sense, often matching against roughly the first
quarter of a resume (usually just the header, contact info, and an
objective line).

**The fix:** `build_resume_embedding_text()` / `build_job_embedding_text()`
in `search_service.py` now put skills and years of experience *first*,
ahead of the raw resume text — so they're guaranteed to survive truncation
no matter how long the resume is or where the skills section happens to
land in it. I wrote a real test demonstrating this: a synthetic resume with
its skills section near the end had all 4 skills verifiably absent from
the first 300 characters under the old approach, and all 4 present under
the new one. This is wired into every place a resume or job gets embedded:
initial upload, batch upload, background reprocessing, and job ranking.

**Existing indexed resumes won't benefit automatically** — the fix only
applies going forward. Added `POST /api/resumes/reindex` (and a "Rebuild
search index" button on the Resumes page) to re-embed everything already
uploaded with the corrected strategy without re-uploading each file.

**Also fixed while in there:** upload endpoints used
`temp_{filename}`/`temp_apply_{filename}` for temp file paths with no
uniqueness — two people uploading a same-named `resume.pdf` around the same
time could collide and corrupt each other's upload. Now includes a UUID.

**What I did not change:** the embedding model itself. A larger, more
accurate model (e.g. `all-mpnet-base-v2`) would likely improve match
quality further, but it's slower — directly in tension with the latency
ask above. I'm flagging this trade-off rather than picking one silently;
happy to swap it if you'd rather prioritize accuracy over speed for search
specifically.

## Verified vs. not, honestly
Everything pure-Python (the embedding-text builders, the batch-similarity
math, `rank_applications`' branching, the N+1 fix's logic) was actually
run and tested in this pass, not just syntax-checked — see the test output
in this conversation. The LangSmith middleware and the real FastAPI/
SQLAlchemy request-handling stack still can't be exercised end-to-end here
(no network to install `langsmith`/`fastapi`/`sqlalchemy` in this sandbox) —
run a real request through and confirm a trace appears at
smith.langchain.com, and click through one AI Hub email generation +
send, before relying on either in front of real candidates.

---

# Fix: email draft coming back blank with a "success" toast

Reported from a real run: clicking "Generate email" showed the green
"Draft ready below" toast, but nothing appeared below the button.

**Root cause, confirmed with a test:** `OutreachEmailResponse` requires
`subject_line`/`email_body` as `str`, and Pydantic accepts an empty string
`""` as perfectly valid — so a technically well-formed but content-less LLM
response (`{"subject_line": "Job Offer", "email_body": ""}`) was treated as
a success. This is much more likely with no `GROQ_API_KEY` set, since the
app then falls back to a small local Ollama model (`llama3.2:3b`), which is
far less reliable at strictly following a "respond with ONLY valid JSON"
instruction than a hosted model like Groq's Llama-3.1-8b.

**Fixed in `llm_service.py`:** `generate_outreach_email` now checks that
both fields are non-empty after `.strip()` and treats blank content as a
failure, not a success — so the caller shows a real error instead of the
frontend silently rendering nothing. Verified with a real test (stubbing
just enough of `pydantic`/`requests` to run the actual function): a
simulated blank-body response is now correctly rejected, and a well-formed
response still succeeds exactly as before.

**Also hardened the frontend** (`ai-hub.tsx`) as a second line of defense:
if a generation ever reports success with nothing in it, an explicit red
message now explains that rather than leaving blank space where the draft
should be.

**If you hit this again:** it's worth setting `GROQ_API_KEY` in
`backend/.env` (free tier at console.groq.com) — the local Ollama fallback
is meant as a no-setup option, not the reliable path for structured JSON
output like this.
