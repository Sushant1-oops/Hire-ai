import { useState } from "react";
import { aiApi } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import Spinner from "../components/Spinner";
import Label from "../components/Label";

export default function JobDescPage() {
  const { token } = useAuth();
  const toast = useToast();

  const [form, setForm] = useState({
    job_title: "",
    job_shorthand: "",
    company: "",
    industry: "",
    experience_level: "mid",
    key_responsibilities: [],
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function generate() {
    if (!form.job_title.trim()) return toast("Enter a job title", "error");
    setLoading(true);
    const res = await aiApi.generateJobDescription(form, token);
    setLoading(false);
    if (res.error || !res.data) return toast(res.message || "Generation failed", "error");
    setResult(res.data);
    toast("Job description generated!", "success");
  }

  function copyAll() {
    if (!result) return;
    const text = [
      result.job_description,
      "",
      "Required Skills:",
      result.required_skills?.map((s) => `  • ${s}`).join("\n"),
      "",
      "Nice to Have:",
      result.nice_to_have_skills?.map((s) => `  • ${s}`).join("\n"),
    ].join("\n");
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast("Copied to clipboard", "success");
    });
  }

  const fields = [
    { key: "job_title",     label: "Job Title",       type: "text", placeholder: "e.g. Senior Backend Engineer",  required: true },
    { key: "job_shorthand", label: "Job Shorthand",   type: "text", placeholder: "e.g. SBE, PM, ML Eng…" },
    { key: "company",       label: "Company",         type: "text", placeholder: "Acme Corp" },
    { key: "industry",      label: "Industry",        type: "text", placeholder: "Fintech, Healthcare, SaaS…" },
  ];

  return (
    <div className="anim-fadeup">
      <PageHeader
        title="Job Description Generator"
        subtitle="AI-crafted job descriptions with required and nice-to-have skill lists"
      />

      <div
        style={{ display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: 22, alignItems: "start" }}
      >
        {/* Form */}
        <SectionCard style={{ padding: 22 }}>
          <div className="font-display" style={{ fontSize: 14, fontWeight: 700, marginBottom: 18 }}>
            Role Details
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
            {fields.map(({ key, label, type, placeholder, required }) => (
              <div key={key}>
                <Label>{label}{required && <span style={{ color: "var(--rose)", marginLeft: 3 }}>*</span>}</Label>
                <input
                  className="input"
                  type={type}
                  placeholder={placeholder}
                  value={form[key]}
                  onChange={set(key)}
                />
              </div>
            ))}

            <div>
              <Label>Experience Level</Label>
              <select className="select" value={form.experience_level} onChange={set("experience_level")}>
                <option value="junior">Junior (0–2 years)</option>
                <option value="mid">Mid-Level (2–5 years)</option>
                <option value="senior">Senior (5+ years)</option>
                <option value="lead">Lead / Principal</option>
              </select>
            </div>

            <button
              className="btn btn-primary"
              onClick={generate}
              disabled={loading}
              style={{ padding: "12px", marginTop: 6 }}
            >
              {loading ? <><Spinner size={15} /> Generating…</> : "⊡ Generate Job Description"}
            </button>
          </div>
        </SectionCard>

        {/* Output */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {result ? (
            <>
              {/* JD text */}
              <SectionCard style={{ padding: 22 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    marginBottom: 14,
                  }}
                >
                  <div className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
                    Generated Description
                  </div>
                  <button
                    className="btn btn-emerald"
                    onClick={copyAll}
                    style={{ padding: "6px 14px", fontSize: 13 }}
                  >
                    {copied ? "✓ Copied!" : "Copy All"}
                  </button>
                </div>
                <pre
                  style={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 9,
                    padding: 16,
                    fontSize: 13.5,
                    color: "var(--text-dim)",
                    fontFamily: "var(--font-body)",
                    lineHeight: 1.85,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    maxHeight: 340,
                    overflowY: "auto",
                  }}
                >
                  {result.job_description}
                </pre>
              </SectionCard>

              {/* Skill tags */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                {[
                  { title: "✅ Required Skills",   items: result.required_skills,      cls: "tag-emerald" },
                  { title: "⭐ Nice to Have",       items: result.nice_to_have_skills,  cls: "tag-violet"  },
                ].map(({ title, items, cls }) => (
                  <SectionCard key={title} style={{ padding: 18 }}>
                    <div className="font-display" style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 12 }}>
                      {title}
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                      {items?.length ? (
                        items.map((s) => <span key={s} className={`tag ${cls}`}>{s}</span>)
                      ) : (
                        <span style={{ fontSize: 12.5, color: "var(--text-muted)" }}>None</span>
                      )}
                    </div>
                  </SectionCard>
                ))}
              </div>
            </>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 340,
                border: "2px dashed var(--border2)",
                borderRadius: 14,
                color: "var(--text-muted)",
                gap: 10,
              }}
            >
              <div style={{ fontSize: 36, opacity: 0.4 }}>⊡</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>Output will appear here</div>
              <div style={{ fontSize: 13 }}>Fill in the role details and click Generate</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
