import { useState, useEffect, useCallback } from "react";
import { resumeApi } from "../api";
import { useAuth } from "../context/AuthContext";

export function useResumes() {
  const { token } = useAuth();
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchResumes = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    const res = await resumeApi.list(token);
    if (res.data) {
      setResumes(res.data);
    } else {
      setError(res.message || "Failed to fetch resumes");
    }
    setLoading(false);
  }, [token]);

  useEffect(() => {
    fetchResumes();
  }, [fetchResumes]);

  return { resumes, loading, error, refresh: fetchResumes };
}
