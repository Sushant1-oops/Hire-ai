import { useEffect, useState } from "react";
import { aiApi, resumeApi } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import Spinner from "../components/Spinner";
import Label from "../components/Label";

const EMAIL_TYPES = [
  { value: "interview_invite", label: "Interview Invite" },
  { value: "offer",            label: "Job Offer" },
  { value: "rejection",        label: "Rejection" },
  { value: "follow_up",        label: "Follow-up" },
  { value: "thank_you",        label: "Thank You Note" },
  { value: "cold_outreach",    label: "Cold Outreach" },
];

export default function OutreachEmailPage() {
  const { token } = useAuth();
  const toast = useToast();

  const [resumes, setResumes] = useState([]);
  const [form, setForm] = useState({
    resume_id: "",
    email_type: "interview_invite",
    job_title: "",
    company_name: "",
    contact_person: "",
    interview_date: "",
    interview_time: "",
    interview_location: "",
  });
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [candidateEmail, setCandidateEmail] = useState("");
  const [copied, setCopied] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  useEffect(() => {
    resumeApi.list(token).then((r) => { if (r.data) setResumes(r.data); });
  }, [token]);

  // Auto-populate candidate email when resume is selected
  useEffect(() => {
    if (form.resume_id) {
      const resume = resumes.find((r) => r.id === +form.resume_id);
      if (resume?.candidate_email) {
        setCandidateEmail(resume.candidate_email);
      }
    }
  }, [form.resume_id, resumes]);

  async function generate() {
    if (!form.resume_id) return toast("Select a candidate", "error");
    if (!form.job_title.trim()) return toast("Enter a job title", "error");
    setLoading(true);
    const payload = {
      ...form,
      resume_id: +form.resume_id,
      interview_date:     form.interview_date     || null,
      interview_time:     form.interview_time     || null,
      interview_location: form.interview_location || null,
      company_name:       form.company_name       || null,
      contact_person:     form.contact_person     || null,
    };
    const res = await aiApi.generateEmail(payload, token);
    setLoading(false);
    if (res.error || !res.data) return toast(res.message || "Generation failed", "error");
    setResult(res.data);
    if (res.data.candidate_email) setCandidateEmail(res.data.candidate_email);
    toast("Email generated!", "success");
  }

  function copyEmail() {
    if (!result) return;
    const text = `Subject: ${result.subject_line}\n\n${result.email_body}`;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast("Copied to clipboard", "success");
    });
  }

  async function sendEmail() {
    if (!result) return;
    if (!candidateEmail) return toast("No recipient email address", "error");

    setSending(true);
    const res = await aiApi.sendEmail({
      to_email: candidateEmail,
      subject: result.subject_line,
      body: result.email_body,
    }, token);
    setSending(false);

    if (res.error) {
      return toast(res.message || "Failed to send email", "error");
    }
    toast("✓ Email sent successfully!", "success");
  }

  const showInterviewFields = form.email_type === "interview_invite";

  return (
    <div className="anim-fadeup">
      <PageHeader
        title="Outreach Email"
        subtitle="Generate & send personalized candidate emails · interview invites, offers, rejections & more"
      />

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: 22, alignItems: "start" }}>
        {/* Form */}
        <SectionCard style={{ padding: 22 }}>
          <div className="font-display" style={{ fontSize: 14, fontWeight: 700, marginBottom: 18 }}>
            Email Details
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 15 }}>
            <div>
              <Label>Candidate</Label>
              <select className="select" value={form.resume_id} onChange={set("resume_id")}>
                <option value="">— Select a candidate —</option>
                {resumes.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.candidate_name || `Resume #${r.id}`}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <Label>Email Type</Label>
              <select className="select" value={form.email_type} onChange={set("email_type")}>
                {EMAIL_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            <div>
              <Label>Job Title</Label>
              <input className="input" placeholder="e.g. Backend Engineer" value={form.job_title} onChange={set("job_title")} />
            </div>

            <div>
              <Label>Company Name</Label>
              <input className="input" placeholder="Acme Corp" value={form.company_name} onChange={set("company_name")} />
            </div>

            <div>
              <Label>Your Name / Contact Person</Label>
              <input className="input" placeholder="Jane Smith, HR Manager" value={form.contact_person} onChange={set("contact_person")} />
            </div>

            {showInterviewFields && (
              <>
                <div>
                  <Label>Interview Date</Label>
                  <input className="input" type="date" value={form.interview_date} onChange={set("interview_date")} />
                </div>
                <div>
                  <Label>Interview Time</Label>
                  <input className="input" type="time" value={form.interview_time} onChange={set("interview_time")} />
                </div>
                <div>
                  <Label>Location / Meeting Link</Label>
                  <input className="input" placeholder="Zoom link or office address" value={form.interview_location} onChange={set("interview_location")} />
                </div>
              </>
            )}

            <button
              className="btn btn-primary"
              onClick={generate}
              disabled={loading}
              style={{ padding: "12px", marginTop: 4 }}
            >
              {loading ? <><Spinner size={15} /> Generating…</> : "◎ Generate Email"}
            </button>
          </div>
        </SectionCard>

        {/* Preview */}
        <div>
          {result ? (
            <SectionCard style={{ padding: 22 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
                <div className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
                  Generated Email
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-ghost" onClick={copyEmail} style={{ padding: "6px 16px", fontSize: 13 }}>
                    {copied ? "✓ Copied!" : "Copy"}
                  </button>
                  <button
                    className="btn btn-emerald"
                    onClick={sendEmail}
                    disabled={sending || !candidateEmail}
                    style={{ padding: "6px 16px", fontSize: 13 }}
                    title={candidateEmail ? `Send to ${candidateEmail}` : "No recipient email"}
                  >
                    {sending ? <><Spinner size={13} /> Sending…</> : `✉ Send${candidateEmail ? ` to ${candidateEmail}` : ""}`}
                  </button>
                </div>
              </div>

              {/* Recipient */}
              {candidateEmail && (
                <div style={{ padding: "8px 14px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 9, marginBottom: 10, fontSize: 13 }}>
                  <span className="field-label" style={{ marginRight: 6 }}>To:</span>
                  <span>{candidateEmail}</span>
                </div>
              )}

              {/* Subject */}
              <div style={{ padding: "10px 14px", background: "var(--amber-dim)", border: "1px solid rgba(245,158,11,0.2)", borderRadius: 9, marginBottom: 14 }}>
                <span className="field-label" style={{ marginRight: 6 }}>Subject:</span>
                <span className="font-display" style={{ fontSize: 14, fontWeight: 600 }}>{result.subject_line}</span>
              </div>

              {/* Body */}
              <pre style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 9, padding: 16, fontSize: 13.5, color: "var(--text-dim)", fontFamily: "var(--font-body)", lineHeight: 1.85, whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 480, overflowY: "auto" }}>
                {result.email_body}
              </pre>
            </SectionCard>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 320, border: "2px dashed var(--border2)", borderRadius: 14, color: "var(--text-muted)", gap: 10 }}>
              <div style={{ fontSize: 36, opacity: 0.4 }}>◎</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>Email preview will appear here</div>
              <div style={{ fontSize: 13 }}>Fill in the form and click Generate</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
