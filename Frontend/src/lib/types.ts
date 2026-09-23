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

export interface ResumeDetail extends Resume {
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
  recommendation: string;
  rank: number;
}

export interface SearchSummary {
  total_in_pool: number;
  total_scored: number;
  total_above_threshold: number;
  filtered_out: number;
  score_threshold?: number;
}

export interface DashboardStats {
  total_resumes: number;
  avg_experience: number;
  top_skills: { skill: string; count: number }[];
  experience_distribution: { range: string; count: number }[];
  recent_searches: { query: string; results_count: number; created_at?: string }[];
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
  subject_line: string;
  email_body: string;
  candidate_email?: string | null;
}

export interface GeneratedJobDescription {
  job_description: string;
  required_skills: string[];
  nice_to_have_skills: string[];
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
  recommendation: string;
  rank: number;
}
