import { apiRequest } from "./api";
import type {
  ApplicationStatus,
  DashboardStats,
  GeneratedJobDescription,
  InterviewQuestions,
  Job,
  MatchAnalysis,
  OutreachEmail,
  PublicJob,
  RankedApplication,
  Resume,
  ResumeDetail,
  SearchResult,
  SearchSummary,
} from "./types";

export const dashboardStatsQuery = () => ({
  queryKey: ["dashboard", "stats"],
  queryFn: () => apiRequest<DashboardStats>("/api/dashboard/stats"),
});

export const resumesQuery = () => ({
  queryKey: ["resumes"],
  queryFn: () => apiRequest<Resume[]>("/api/resumes"),
});

export const resumeQuery = (id: string | number) => ({
  queryKey: ["resumes", String(id)],
  queryFn: () => apiRequest<ResumeDetail>(`/api/resumes/${id}`),
  enabled: !!id,
});

export interface SearchPayload {
  query: string;
  required_skills: string[];
  nice_to_have_skills: string[];
  min_experience: number;
  job_description?: string | undefined;
  top_k?: number;
}

export const runSearch = (payload: SearchPayload) =>
  apiRequest<{ results: SearchResult[]; summary: SearchSummary }>("/api/search", {
    body: payload,
  });

export const uploadResumes = (files: File[]) => {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return apiRequest<{ successful: unknown[]; failed: unknown[] }>("/api/resumes/upload-batch", {
    formData,
  });
};

export const deleteResume = (id: string | number) =>
  apiRequest<void>(`/api/resumes/${id}`, { method: "DELETE" });

export const reindexResumes = () => apiRequest<void>("/api/resumes/reindex", { method: "POST" });

export const analyzeMatch = (payload: { resume_id: string | number; job_description: string }) =>
  apiRequest<MatchAnalysis>("/api/ai/analyze-match", { body: payload });

export const generateQuestions = (payload: {
  resume_id: string | number;
  job_title: string;
  job_description?: string | undefined;
  required_skills?: string[] | undefined;
}) => apiRequest<InterviewQuestions>("/api/ai/generate-questions", { body: payload });

export const generateEmail = (payload: {
  resume_id: string | number;
  email_type: string;
  job_title: string;
  company_name?: string | undefined;
  contact_person?: string | undefined;
  interview_date?: string | undefined;
  interview_time?: string | undefined;
  interview_location?: string | undefined;
}) => apiRequest<OutreachEmail>("/api/ai/generate-email", { body: payload });

export const sendEmail = (payload: { to_email: string; subject: string; body: string }) =>
  apiRequest<void>("/api/email/send", { body: payload });

export const generateJobDescription = (payload: {
  job_title: string;
  job_shorthand: string;
  company_name?: string | undefined;
  required_skills?: string[] | undefined;
}) => apiRequest<GeneratedJobDescription>("/api/ai/generate-job-description", { body: payload });



export const jobsQuery = () => ({
  queryKey: ["jobs"],
  queryFn: () => apiRequest<Job[]>("/api/jobs"),
});

export const jobQuery = (jobId: string | number) => ({
  queryKey: ["jobs", String(jobId)],
  queryFn: () => apiRequest<Job>(`/api/jobs/${jobId}`),
  enabled: !!jobId,
});

export const jobApplicationsQuery = (jobId: string | number) => ({
  queryKey: ["jobs", String(jobId), "applications"],
  queryFn: () =>
    apiRequest<{ job: Job; applications: RankedApplication[] }>(`/api/jobs/${jobId}/applications`),
  enabled: !!jobId,
});

export const createJob = (payload: {
  title: string;
  description: string;
  location?: string | undefined;
  experience_min?: number | undefined;
  required_skills?: string[] | undefined;
}) => apiRequest<Job>("/api/jobs", { body: payload });

export const setJobStatus = (jobId: string | number, status: "open" | "closed") =>
  apiRequest<Job>(`/api/jobs/${jobId}/status`, { method: "PATCH", body: { status } });

export const setApplicationStatus = (applicationId: string | number, status: ApplicationStatus) =>
  apiRequest<void>(`/api/applications/${applicationId}/status`, {
    method: "PATCH",
    body: { status },
  });



export const publicJobQuery = (slug: string) => ({
  queryKey: ["public-job", slug],
  queryFn: () => apiRequest<PublicJob>(`/api/public/jobs/${slug}`),
  enabled: !!slug,
});

export const submitApplication = (
  slug: string,
  input: { full_name: string; email: string; phone?: string | undefined; resume: File },
) => {
  const formData = new FormData();
  formData.append("full_name", input.full_name);
  formData.append("email", input.email);
  if (input.phone) formData.append("phone", input.phone);
  formData.append("resume", input.resume);
  return apiRequest<{ application_id: number; job_title: string }>(
    `/api/public/jobs/${slug}/apply`,
    {
      formData,
    },
  );
};
