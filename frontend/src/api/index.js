// ─── Configure your backend URL here ───────────────────────────
// During dev the Vite proxy forwards /api → localhost:8000, so leave
// VITE_API_URL empty.  In production set it to your backend origin.
export const API_BASE = import.meta.env.VITE_API_URL || "";

/**
 * Core fetch wrapper.
 * Automatically attaches Bearer token and Content-Type.
 * Returns parsed JSON or an error object.
 */
export async function api(path, options = {}, token = null) {
  const headers = { ...options.headers };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData — browser sets it with boundary
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

    // Handle 401 globally — clear stale tokens
    if (res.status === 401) {
      localStorage.removeItem("hireai_token");
      localStorage.removeItem("hireai_user");
      // Only redirect if not already on login page
      if (!window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
      return { error: true, message: "Session expired. Please log in again." };
    }

    const data = await res.json();
    return data;
  } catch (err) {
    return { error: true, message: err.message || "Network error" };
  }
}

// ─── Auth ────────────────────────────────────────────────────────
export const authApi = {
  login: (email, password) =>
    api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  register: (username, email, password, firstName, lastName, company) =>
    api("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({
        username,
        email,
        password,
        first_name: firstName || "",
        last_name: lastName || "",
        company: company || "",
      }),
    }),

  me: (token) => api("/api/auth/me", {}, token),

  refresh: (refreshToken) =>
    api("/api/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),
};

// ─── Health ──────────────────────────────────────────────────────
export const healthApi = {
  check: () => api("/health"),
  setup: () => api("/api/setup", { method: "POST" }),
};

// ─── Resumes ─────────────────────────────────────────────────────
export const resumeApi = {
  list: (token) => api("/api/resumes", {}, token),

  get: (id, token) => api(`/api/resumes/${id}`, {}, token),

  upload: (file, token) => {
    const fd = new FormData();
    fd.append("file", file);
    return api("/api/resumes/upload", { method: "POST", body: fd }, token);
  },

  uploadBatch: (files, token) => {
    const fd = new FormData();
    for (const file of files) {
      fd.append("files", file);
    }
    return api("/api/resumes/upload-batch", { method: "POST", body: fd }, token);
  },

  delete: (id, token) =>
    api(`/api/resumes/${id}`, { method: "DELETE" }, token),

  stats: (token) => api("/api/dashboard/stats", {}, token),
};

// ─── Search ──────────────────────────────────────────────────────
export const searchApi = {
  semantic: (payload, token) =>
    api("/api/search", { method: "POST", body: JSON.stringify(payload) }, token),
};

// ─── AI Features ─────────────────────────────────────────────────
export const aiApi = {
  analyzeMatch: (resumeId, jobDescription, token) =>
    api(
      "/api/ai/analyze-match",
      {
        method: "POST",
        body: JSON.stringify({ resume_id: resumeId, job_description: jobDescription }),
      },
      token
    ),

  generateQuestions: (payload, token) =>
    api(
      "/api/ai/generate-questions",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  generateEmail: (payload, token) =>
    api(
      "/api/ai/generate-email",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  sendEmail: (payload, token) =>
    api(
      "/api/email/send",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),

  generateJobDescription: (payload, token) =>
    api(
      "/api/ai/generate-job-description",
      { method: "POST", body: JSON.stringify(payload) },
      token
    ),
};
