# HireAI — Frontend

React 19 + TanStack Start/Router/Query, Tailwind CSS 4, shadcn/ui (Radix).

## Run

```bash
cp .env.example .env        # VITE_API_BASE_URL -> your backend, default http://localhost:8000
npm install
npm run dev                 # http://localhost:5173
npm run build
```

## Layout

| Path | What lives there |
|---|---|
| `src/routes/_authenticated/` | Signed-in pages: `dashboard`, `jobs/` (list + `$jobId` detail), `resumes`, `search` |
| `src/routes/apply.$slug.tsx` | Public application form (no login) |
| `src/components/` | Feature components: `ai-hub`, `candidate-drawer`, `job-form-dialog`, `add-to-job-dialog`, `skill-input`, `recommendation-badge`, `score-ring` |
| `src/components/ui/` | shadcn primitives (generated, don't hand-edit) |
| `src/lib/api.ts` | `fetch` wrapper: bearer token, single-flight refresh on 401, typed errors |
| `src/lib/queries.ts` | Every backend call + its React Query key. Mutations invalidate by key prefix (`["jobs"]`, `["resumes"]`, `["dashboard"]`) |
| `src/lib/types.ts` | API response types |

## Conventions

- Anything the backend processes asynchronously (resume parsing, scoring) is polled with `refetchInterval` only while something is pending.
- Optional props are typed `T | undefined` because `exactOptionalPropertyTypes` is on.
