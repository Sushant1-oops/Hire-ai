import { useRef, useState } from "react";
import { resumeApi } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { useResumes } from "../hooks/useResumes";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import EmptyState from "../components/EmptyState";
import Modal from "../components/Modal";
import Spinner from "../components/Spinner";

export default function ResumesPage() {
  const { token } = useAuth();
  const toast = useToast();
  const { resumes, loading, refresh } = useResumes();

  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [dragging, setDragging] = useState(false);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deletingId, setDeletingId] = useState(null);

  const fileRef = useRef();

  async function handleUpload(files) {
    if (!files || files.length === 0) return;

    const pdfFiles = Array.from(files).filter((f) =>
      f.name.toLowerCase().endsWith(".pdf")
    );
    if (pdfFiles.length === 0) return toast("Only PDF files are accepted", "error");

    setUploading(true);

    if (pdfFiles.length === 1) {
      setUploadProgress("Processing resume…");
      const res = await resumeApi.upload(pdfFiles[0], token);
      setUploading(false);
      setUploadProgress("");
      if (res.error || !res.data) return toast(res.message || "Upload failed", "error");
      toast(`✓ ${res.data.candidate_name || pdfFiles[0].name} uploaded`, "success");
    } else {
      setUploadProgress(`Processing ${pdfFiles.length} resumes…`);
      const res = await resumeApi.uploadBatch(pdfFiles, token);
      setUploading(false);
      setUploadProgress("");
      if (res.error || !res.data) return toast(res.message || "Batch upload failed", "error");
      const ok = res.data.successful?.length || 0;
      const fail = res.data.failed?.length || 0;
      toast(`✓ ${ok} uploaded${fail ? `, ${fail} failed` : ""}`, ok > 0 ? "success" : "error");
    }
    refresh();
  }

  async function viewDetail(id) {
    setDetailLoading(true);
    setDetail(null);
    const res = await resumeApi.get(id, token);
    setDetailLoading(false);
    if (res.data) setDetail(res.data);
    else toast("Failed to load resume details", "error");
  }

  async function handleDelete(id) {
    setDeletingId(id);
    const res = await resumeApi.delete(id, token);
    setDeletingId(null);
    if (res.error) return toast("Delete failed", "error");
    toast("Resume deleted", "success");
    refresh();
    if (detail?.id === id) setDetail(null);
  }

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files;
    if (f?.length) handleUpload(f);
  };

  return (
    <div className="anim-fadeup">
      <PageHeader
        title="Resume Library"
        subtitle="Upload and manage candidate resumes · PDF only · drag multiple files"
      />

      {/* Drop zone */}
      <div
        className={`drop-zone ${dragging ? "active" : ""}`}
        style={{ marginBottom: 24 }}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !uploading && fileRef.current?.click()}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".pdf"
          multiple
          style={{ display: "none" }}
          onChange={(e) => handleUpload(e.target.files)}
        />
        {uploading ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 12 }}>
            <Spinner />
            <span style={{ color: "var(--amber)", fontWeight: 600 }}>
              {uploadProgress}
            </span>
          </div>
        ) : (
          <>
            <div style={{ fontSize: 34, marginBottom: 10, color: "var(--text-muted)", opacity: 0.6 }}>
              ⊟
            </div>
            <div className="font-display" style={{ fontSize: 15, fontWeight: 700, marginBottom: 5 }}>
              Drop PDFs here or click to browse
            </div>
            <div style={{ fontSize: 13, color: "var(--text-muted)" }}>
              Max 20 MB per file · Multiple files supported · Skills & experience extracted automatically
            </div>
          </>
        )}
      </div>

      {/* Table */}
      <SectionCard>
        <div
          style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "14px 18px", borderBottom: "1px solid var(--border)",
          }}
        >
          <div className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
            All Resumes
          </div>
          <span className="tag tag-dim">{resumes.length} total</span>
        </div>

        {loading ? (
          <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
            {[...Array(4)].map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 46 }} />
            ))}
          </div>
        ) : resumes.length === 0 ? (
          <EmptyState icon="⊟" title="No resumes yet" body="Upload your first PDF to get started" />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Experience</th>
                <th>Skills</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {resumes.map((r) => (
                <tr key={r.id}>
                  <td>
                    <div className="font-display" style={{ fontWeight: 700, fontSize: 13.5 }}>
                      {r.candidate_name || "—"}
                    </div>
                    <div className="font-mono" style={{ fontSize: 10, color: "var(--text-muted)" }}>
                      #{r.id}
                    </div>
                  </td>
                  <td style={{ color: "var(--text-dim)", fontSize: 13 }}>
                    {r.candidate_email || "—"}
                  </td>
                  <td style={{ color: "var(--text-dim)", fontSize: 13 }}>
                    {r.candidate_phone || "—"}
                  </td>
                  <td>
                    {r.experience_years ? (
                      <span className="tag tag-violet font-mono">{r.experience_years}y</span>
                    ) : (
                      <span style={{ color: "var(--text-muted)" }}>—</span>
                    )}
                  </td>
                  <td style={{ maxWidth: 220 }}>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                      {(r.skills || []).slice(0, 4).map((s) => (
                        <span key={s} className="tag tag-dim">{s}</span>
                      ))}
                      {(r.skills || []).length > 4 && (
                        <span className="tag tag-dim">+{r.skills.length - 4}</span>
                      )}
                      {!r.skills?.length && (
                        <span style={{ color: "var(--text-muted)", fontSize: 12 }}>None detected</span>
                      )}
                    </div>
                  </td>
                  <td className="font-mono" style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    {new Date(r.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="btn btn-ghost" onClick={() => viewDetail(r.id)} style={{ padding: "5px 12px", fontSize: 12 }}>
                        View
                      </button>
                      <button
                        className="btn btn-danger"
                        onClick={() => handleDelete(r.id)}
                        disabled={deletingId === r.id}
                        style={{ padding: "5px 12px", fontSize: 12 }}
                      >
                        {deletingId === r.id ? <Spinner size={13} color="var(--rose)" /> : "Delete"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </SectionCard>

      {/* Detail modal */}
      {(detailLoading || detail) && (
        <Modal
          title={detail ? `${detail.candidate_name || "Resume"} — Details` : "Loading…"}
          onClose={() => setDetail(null)}
        >
          {detailLoading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: 40 }}>
              <Spinner size={32} />
            </div>
          ) : detail ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                {[
                  ["Candidate Name", detail.candidate_name || "—"],
                  ["Email", detail.candidate_email || "—"],
                  ["Phone", detail.candidate_phone || "—"],
                  ["Experience", detail.experience_years ? `${detail.experience_years} years` : "—"],
                ].map(([k, v]) => (
                  <div key={k} style={{ padding: "10px 14px", background: "var(--surface)", borderRadius: 9, border: "1px solid var(--border)" }}>
                    <div className="field-label" style={{ marginBottom: 4 }}>{k}</div>
                    <div style={{ fontSize: 13.5, fontWeight: 500 }}>{v}</div>
                  </div>
                ))}
              </div>

              {/* Education */}
              {detail.education?.length > 0 && (
                <div>
                  <div className="field-label" style={{ marginBottom: 8 }}>Education</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6, padding: "12px 14px", background: "var(--surface)", borderRadius: 9, border: "1px solid var(--border)" }}>
                    {detail.education.map((e, i) => (
                      <span key={i} className="tag tag-violet">{e.degree}</span>
                    ))}
                  </div>
                </div>
              )}

              {/* Skills */}
              <div>
                <div className="field-label" style={{ marginBottom: 8 }}>Detected Skills</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, padding: "12px 14px", background: "var(--surface)", borderRadius: 9, border: "1px solid var(--border)", minHeight: 44 }}>
                  {detail.skills?.length ? (
                    detail.skills.map((s) => <span key={s} className="tag tag-amber">{s}</span>)
                  ) : (
                    <span style={{ color: "var(--text-muted)", fontSize: 13 }}>No skills detected</span>
                  )}
                </div>
              </div>

              {/* Text preview */}
              {detail.extracted_text && (
                <div>
                  <div className="field-label" style={{ marginBottom: 8 }}>Text Preview</div>
                  <pre style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 9, padding: 14, fontSize: 12, color: "var(--text-dim)", fontFamily: "var(--font-mono)", lineHeight: 1.65, maxHeight: 200, overflowY: "auto", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                    {detail.extracted_text}
                  </pre>
                </div>
              )}
            </div>
          ) : null}
        </Modal>
      )}
    </div>
  );
}
