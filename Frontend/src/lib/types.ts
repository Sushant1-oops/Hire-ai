export interface AuthTokens {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
}

export interface User {
  id: number;
  email: string;
  username: string;
  first_name: string;
  last_name: string;
  company?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface EducationEntry {
  degree: string;
}

export interface Resume {
  id: number;
  candidate_name?: string | null;
  candidate_email?: string | null;
  candidate_phone?: string | null;
  skills?: string[];
  experience_years?: number | null;
  created_at?: string;
  processing_status?: "pending" | "ready" | "failed" | string;
  processing_error?: string | null;
  needs_review?: boolean;
}

export interface ResumeApplication {
  application_id: number;
  job_id: number;
  job_title: string;
  status: ApplicationStatus;
  score: number | null;
}

export interface ResumeDetail extends Resume {
  applications?: ResumeApplication[];
  education?: EducationEntry[];
  extracted_text?: string;
  name_confidence?: number | null;
  used_ocr?: boolean;
  unrecognised_skills?: string[];
}

export interface SearchResult {
  resume_id: number;
  candidate_name?: string | null;
  candidate_email?: string | null;
  candidate_phone?: string | null;
  experience_years?: number | null;
  skills?: string[];
  final_score: number;
  semantic_similarity: number;
  experience_match: number;
  skill_overlap: number;
  matched_skills: string[];
  missing_skills: string[];
  unverified_skills?: string[];
  recommendation: string;
  evidence_snippet?: string;
  rank: number;
}

export interface SearchSummary {
  total_in_pool: number;
  total_scored: number;
  total_above_threshold: number;
  filtered_out: number;
  score_threshold?: number;
}

export interface DashboardData {
  kpis: {
    open_jobs: number;
    closed_jobs: number;
    total_applications: number;
    awaiting_decision: number;
    in_interview_stage: number;
    hired: number;
    library_size: number;
  };
  pipeline: { status: ApplicationStatus; count: number }[];
  top_candidates: {
    application_id: number;
    job_id: number;
    resume_id: number;
    status: ApplicationStatus;
    score: number;
    recommendation: string;
    job_title: string;
    candidate_name: string | null;
  }[];
  jobs: {
    id: number;
    title: string;
    location: string | null;
    applicants: number;
    new: number;
    in_pipeline: number;
    top_score: number | null;
  }[];
  library: { processing: number; failed: number; needs_review: number };
}

export interface MatchEvidence {
  claim: string;
  supported: boolean;
  similarity?: number;
  chunk_id?: number | null;
  chunk_index?: number;
  snippet?: string;
}

export interface MatchAnalysis {
  recommendation: string;
  match_score: number;
  explanation: string;
  strengths: string[];
  weaknesses: string[];
  missing_skills: string[];
  matched_skills?: string[];
  unverified_skills?: string[];
  score_breakdown?: { semantic_similarity: number; skill_overlap: number; experience_match: number };
  job_id?: number | null;
  evidence?: MatchEvidence[];
  security_flags?: string[];
  ai_explanation_available?: boolean;
}

export interface InterviewQuestions {
  technical_questions: string[];
  behavioral_questions: string[];
  practical_tasks: string[];
}

export interface OutreachEmail {
  id?: number;
  subject_line: string;
  email_body: string;
  candidate_email?: string | null;
}

export interface GeneratedJobDescription {
  job_description: string;
  required_skills: string[];
  nice_to_have_skills: string[];
  experience_min?: number | null;
}

export interface Job {
  id: number;
  public_slug: string;
  title: string;
  location?: string | null;
  experience_min?: number | null;
  description: string;
  required_skills?: string[];
  status: "open" | "closed";
  created_at?: string;
  application_count?: number;
  new_count?: number;
  in_pipeline?: number;
  top_score?: number | null;
}

export interface PublicJob {
  title: string;
  location?: string | null;
  experience_min?: number | null;
  description: string;
  required_skills: string[];
}

export type ApplicationStatus =
  "received" | "screened" | "shortlisted" | "rejected" | "interview" | "hired";

export interface RankedApplication {
  application_id: number;
  resume_id: number;
  candidate_name?: string | null;
  candidate_email?: string | null;
  candidate_phone?: string | null;
  experience_years?: number | null;
  status: ApplicationStatus;
  source: "form" | "email" | "manual";
  applied_at?: string;
  processing_status: "pending" | "ready" | "failed";
  processing_error?: string | null;
  final_score: number;
  semantic_similarity: number;
  experience_match: number;
  skill_overlap: number;
  matched_skills: string[];
  missing_skills: string[];
  unverified_skills?: string[];
  recommendation: string;
  /** null while the resume is still processing or has failed */
  rank: number | null;
}
