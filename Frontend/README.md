# HireWise AI

Act as an expert Full-Stack Frontend Developer. I have a FastAPI backend for an "AI Semantic Hiring Assistant" (HireAI) and I need you to generate a complete, production-ready frontend.

Tech Stack Requirements

Framework: Next.js 14 (App Router) or React with Vite.

Styling: Tailwind CSS + Shadcn UI (for clean, modern, accessible components).

Animations: Framer Motion (for professional page transitions, list staggers, and interactive hover states).

State Management & Data Fetching: React Query (TanStack Query) for API calls, caching, and loading states.

Forms & Validation: React Hook Form + Zod.

Design & UX Guidelines

Theme: Clean, modern SaaS aesthetic. Dark sidebar navigation, light main content area. Use deep blues, crisp whites, and subtle slate grays.

Animations: Subtle and professional. Use stagger animations for list items (resumes, search results). Use smooth layout animations when expanding a candidate's profile. Add a sleek loading skeleton for API calls.

Notifications: Use sonner or react-hot-toast for success/error messages on API actions.

Core Features & Pages to Build

1. Authentication Layout (/login, /register)

Split screen: Left side has a branded gradient/animation highlighting "AI-Powered Hiring". Right side has the auth form.

JWT token management: Store access/refresh tokens in secure cookies or local storage. Include an Axios/Fetch interceptor that automatically refreshes the token if a 401 is received.

Protected Routes: Redirect to /login if unauthenticated.

2. Dashboard (/dashboard)

Stats Cards: Total Resumes, Average Experience, Top Skills (with progress bars), Recent Searches.

Use Recharts or Chart.js to show a beautiful donut chart for "Experience Distribution" and a bar chart for "Top Skills".

API: GET /api/dashboard/stats

3. Resume Management (/resumes)

Upload Zone: A beautiful drag-and-drop area for PDFs. Support multiple file uploads. API: POST /api/resumes/upload-batch

Company-Wise View: Group resumes by the user's company. Display as a responsive grid of candidate cards. Each card shows: Name, Top 3 Skills (as badges), Years of Experience, and a subtle "Match Score" placeholder.

Candidate Detail View: Clicking a card opens a modal or side-drawer showing full parsed details: Contact info, list of all extracted skills, education, and a snippet of their extracted text. API: GET /api/resumes/{id}

4. Semantic Search (/search)

Search Form:

Large textarea for "Query" (e.g., "Senior Python dev with Django experience").

Dynamic tag input for "Required Skills" and "Nice-to-have Skills".

Sliders/Inputs for "Min Experience".

Optional Job Description text area (to auto-extract required skills).

Results Page:

API: POST /api/search

Display results as ranked cards. Each card must visually represent the scoring system:

Circular progress ring for final_score.

Smaller progress bars for semantic_similarity, experience_match, and skill_overlap.

Badges for matched_skills (green) and missing_skills (red).

Tag for recommendation (Strong Hire = green, Consider = yellow, Weak Fit = gray).

Include a button on each result: "Analyze Match" and "Generate Questions".

5. AI Recruitment Hub (Drawer/Modal triggered from Search/Resumes)

Match Analysis: API POST /api/ai/analyze-match. Show strengths, weaknesses, and a generated explanation in a clean, formatted layout.

Interview Questions: API POST /api/ai/generate-questions. Display generated technical, behavioral, and practical questions in an accordion or tabbed view.

Email Generation: API POST /api/ai/generate-email. Form to select email type (interview invite, rejection, etc.) and a beautifully rendered email preview with a "Send Email" button (API POST /api/email/send).

JD Generator: API POST /api/ai/generate-job-description. Form to input a brief summary, outputting a rich-text formatted Job Description and lists of required/nice-to-have skills.

API Contract Reference

Base URL: http://localhost:8000

All protected routes require header: Authorization: Bearer <token>

Auth: POST /api/auth/register, POST /api/auth/login, POST /api/auth/refresh

Resumes: POST /api/resumes/upload, GET /api/resumes, GET /api/resumes/{id}

Search: POST /api/search

AI: POST /api/ai/analyze-match, POST /api/ai/generate-questions, POST /api/ai/generate-email, POST /api/ai/generate-job-description

Instructions

Generate the project structure and package.json with all necessary dependencies.

Create the API client with React Query setup and JWT interceptors.

Build the Auth pages with validation.

Build the Dashboard with charts.

Build the Resumes page with the drag-and-drop uploader and detail view.

Build the Search page with the advanced filters and visual scoring rings/bars.

Implement the AI Hub modal/drawer for generating questions and emails.

Wrap everything in a responsive, animated layout using Framer Motion.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/567c1561-a361-476e-9893-121d7c8f3fd4).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
