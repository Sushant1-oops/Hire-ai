import { useEffect, useState } from "react";
import { aiApi, resumeApi } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import RecommendationBadge from "../components/RecommendationBadge";
import Spinner from "../components/Spinner";
import Label from "../components/Label";

function ListPanel({ title, items, tagCls, icon }) {
  return (
    <SectionCard style={{ padding: 18 }}>
      <div
        className="font-display"
        style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 12 }}
      >
        {icon} {title}
      </div>
      {items?.length ? (
        <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 7 }}>
          {items.map((item, i) => (
            <li key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
              <span className={`tag ${tagCls}`} style={{ marginTop: 2, flexShrink: 0 }}>·</span>
              <span style={{ fontSize: 13, color: "var(--text-dim)", lineHeight: 1.55 }}>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div style={{ fontSize: 13, color: "var(--text-muted)" }}>None noted</div>
      )}
    </SectionCard>
  );
}

export default function AIMatchPage() {
  const { token } = useAuth();
  const toast = useToast();

  const [resumes, setResumes] = useState([]);
  const [resumeId, setResumeId] = useState("");
  const [jobDesc, setJobDesc] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    resumeApi.list(token).then((r) => { if (r.data) setResumes(r.data); });
  }, [token]);

  async function analyze() {
    if (!resumeId) return toast("Select a resume", "error");
    if (!jobDesc.trim()) return toast("Enter a job description", "error");
    setLoading(true);
    const res = await aiApi.analyzeMatch(+resumeId, jobDesc, token);
    setLoading(false);
    if (res.error || !res.data) return toast(res.message || "Analysis failed", "error");
    setResult(res.data);
    toast("Analysis complete", "success");
  }

  const scoreColor = (s) =>
    s >= 0.7 ? "var(--emerald)" : s >= 0.5 ? "var(--amber)" : "var(--rose)";

  return (
    <div className="anim-fadeup">
      <PageHeader
        title="AI Match Analysis"
        subtitle="Deep AI analysis of how well a candidate fits a specific role"
      />

      {/* Input panel */}
      <SectionCard style={{ padding: 22, marginBottom: 22 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
            marginBottom: 16,
          }}
        >
          <div>
            <Label>Candidate Resume</Label>
            <select
              className="select"
              value={resumeId}
              onChange={(e) => setResumeId(e.target.value)}
            >
              <option value="">— Select a resume —</option>
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.candidate_name || `Resume #${r.id}`}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ marginBottom: 18 }}>
          <Label>Job Description</Label>
          <textarea
            className="textarea"
            rows={5}
            placeholder="Paste the full job description here…"
            value={jobDesc}
            onChange={(e) => setJobDesc(e.target.value)}
          />
        </div>

        <button
          className="btn btn-primary"
          onClick={analyze}
          disabled={loading}
          style={{ padding: "11px 28px" }}
        >
          {loading ? <><Spinner size={15} /> Analyzing with AI…</> : "⊛ Analyze Match"}
        </button>
      </SectionCard>

      {/* Result */}
      {result && (
        <div className="anim-fadeup" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Score header */}
          <SectionCard
            style={{
              padding: "20px 24px",
              borderColor: "var(--border2)",
            }}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 20 }}>
              <div
                style={{
                  textAlign: "center",
                  padding: "12px 20px",
                  background: "var(--surface)",
                  borderRadius: 12,
                  border: "1px solid var(--border)",
                  flexShrink: 0,
                }}
              >
                <div className="field-label" style={{ marginBottom: 5 }}>Match Score</div>
                <div
                  className="font-display"
                  style={{
                    fontSize: 38,
                    fontWeight: 900,
                    color: scoreColor(result.match_score || 0),
                    lineHeight: 1,
                  }}
                >
                  {Math.round((result.match_score || 0) * 100)}%
                </div>
              </div>
              <div style={{ paddingTop: 4 }}>
                <div style={{ marginBottom: 10 }}>
                  <RecommendationBadge recommendation={result.recommendation} />
                </div>
                <p style={{ fontSize: 14, color: "var(--text-dim)", lineHeight: 1.7 }}>
                  {result.explanation}
                </p>
              </div>
            </div>
          </SectionCard>

          {/* Breakdown */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
            <ListPanel title="Strengths"      items={result.strengths}      tagCls="tag-emerald" icon="💪" />
            <ListPanel title="Weaknesses"     items={result.weaknesses}     tagCls="tag-rose"    icon="⚠" />
            <ListPanel title="Missing Skills" items={result.missing_skills} tagCls="tag-amber"   icon="🔧" />
          </div>
        </div>
      )}
    </div>
  );
}
