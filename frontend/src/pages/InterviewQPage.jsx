import { useEffect, useState } from "react";
import { aiApi, resumeApi } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import EmptyState from "../components/EmptyState";
import Spinner from "../components/Spinner";
import Label from "../components/Label";

function QuestionList({ title, items, color, mono }) {
  return (
    <SectionCard style={{ padding: 20 }}>
      <div
        className="font-display"
        style={{ fontSize: 14, fontWeight: 700, color, marginBottom: 14 }}
      >
        {title}
      </div>
      {items?.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {items.map((q, i) => (
            <div
              key={i}
              style={{
                display: "flex",
                gap: 10,
                padding: "11px 14px",
                background: "var(--surface)",
                borderRadius: 9,
                border: "1px solid var(--border)",
              }}
            >
              <span
                className="font-mono"
                style={{
                  fontSize: 10,
                  color: color,
                  minWidth: 22,
                  paddingTop: 2,
                  fontWeight: 700,
                }}
              >
                Q{i + 1}
              </span>
              <span
                style={{
                  fontSize: 13.5,
                  color: "var(--text-dim)",
                  lineHeight: 1.6,
                }}
              >
                {q}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState icon="⊞" title="None generated" body="" />
      )}
    </SectionCard>
  );
}

export default function InterviewQPage() {
  const { token } = useAuth();
  const toast = useToast();

  const [resumes, setResumes] = useState([]);
  const [resumeId, setResumeId] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [level, setLevel] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    resumeApi.list(token).then((r) => { if (r.data) setResumes(r.data); });
  }, [token]);

  async function generate() {
    if (!resumeId) return toast("Select a resume", "error");
    if (!jobTitle.trim()) return toast("Enter a job title", "error");
    setLoading(true);
    const res = await aiApi.generateQuestions(
      { resume_id: +resumeId, job_title: jobTitle, candidate_level: level || null },
      token
    );
    setLoading(false);
    if (res.error || !res.data) return toast(res.message || "Generation failed", "error");
    setResult(res.data);
    toast("Questions generated!", "success");
  }

  return (
    <div className="anim-fadeup">
      <PageHeader
        title="Interview Questions"
        subtitle="AI-tailored technical, behavioral & practical questions based on the candidate's profile"
      />

      {/* Config panel */}
      <SectionCard style={{ padding: 22, marginBottom: 22 }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 16,
            marginBottom: 18,
          }}
        >
          <div>
            <Label>Candidate Resume</Label>
            <select
              className="select"
              value={resumeId}
              onChange={(e) => setResumeId(e.target.value)}
            >
              <option value="">— Select —</option>
              {resumes.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.candidate_name || `Resume #${r.id}`}
                </option>
              ))}
            </select>
          </div>
          <div>
            <Label>Job Title</Label>
            <input
              className="input"
              placeholder="e.g. Senior Software Engineer"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
            />
          </div>
          <div>
            <Label>Level (optional)</Label>
            <select
              className="select"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
            >
              <option value="">Auto-detect from resume</option>
              <option value="fresher">Fresher (0-2y)</option>
              <option value="intermediate">Intermediate (2-5y)</option>
              <option value="experienced">Experienced (5y+)</option>
            </select>
          </div>
        </div>

        <button
          className="btn btn-primary"
          onClick={generate}
          disabled={loading}
          style={{ padding: "10px 24px" }}
        >
          {loading ? <><Spinner size={15} /> Generating…</> : "⊞ Generate Questions"}
        </button>
      </SectionCard>

      {/* Results */}
      {result && (
        <div
          className="anim-stagger anim-fadeup"
          style={{ display: "flex", flexDirection: "column", gap: 14 }}
        >
          <QuestionList
            title="⚙ Technical Questions"
            items={result.technical_questions}
            color="var(--violet)"
          />
          <QuestionList
            title="🤝 Behavioral Questions"
            items={result.behavioral_questions}
            color="var(--amber)"
          />
          <QuestionList
            title="🛠 Practical Tasks"
            items={result.practical_tasks}
            color="var(--emerald)"
          />
        </div>
      )}
    </div>
  );
}
