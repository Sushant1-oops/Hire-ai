import { useState } from "react";
import { searchApi } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import ScoreBar from "../components/ScoreBar";
import RecommendationBadge from "../components/RecommendationBadge";
import EmptyState from "../components/EmptyState";
import Spinner from "../components/Spinner";
import Label from "../components/Label";

export default function SearchPage() {
  const { token } = useAuth();
  const toast = useToast();

  const [query, setQuery] = useState("");
  const [reqSkills, setReqSkills] = useState("");
  const [niceSkills, setNiceSkills] = useState("");
  const [minExp, setMinExp] = useState("");
  const [niceExp, setNiceExp] = useState("");
  const [topK, setTopK] = useState(10);
  const [showFilters, setShowFilters] = useState(false);

  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  async function handleSearch() {
    if (!query.trim()) return toast("Enter a search query", "error");
    setLoading(true);
    const payload = {
      query: query.trim(),
      top_k: topK,
      required_skills: reqSkills ? reqSkills.split(",").map((s) => s.trim()).filter(Boolean) : null,
      nice_to_have_skills: niceSkills ? niceSkills.split(",").map((s) => s.trim()).filter(Boolean) : null,
      min_experience: minExp ? parseFloat(minExp) : null,
      nice_to_have_experience: niceExp ? parseFloat(niceExp) : null,
    };
    const res = await searchApi.semantic(payload, token);
    setLoading(false);
    if (res.error || !res.data) return toast(res.message || "Search failed", "error");
    setResults(res.data);
    setSearched(true);
    toast(`Found ${res.data.length} candidates`, "success");
  }

  const rankColor = (rank) => {
    if (rank === 1) return "var(--amber)";
    if (rank === 2) return "var(--violet)";
    if (rank === 3) return "var(--cyan)";
    return "var(--text-muted)";
  };

  return (
    <div className="anim-fadeup">
      <PageHeader
        title="Semantic Search"
        subtitle="Natural language candidate search · AI-powered hybrid ranking with skill matching"
      />

      {/* Search panel */}
      <SectionCard style={{ padding: 22, marginBottom: 22 }}>
        <div style={{ marginBottom: 14 }}>
          <Label>Job Description / Requirements</Label>
          <textarea
            className="textarea"
            rows={3}
            placeholder="e.g. Senior Python developer with Django and PostgreSQL experience for a fintech startup…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <button className="btn btn-primary" onClick={handleSearch} disabled={loading} style={{ padding: "10px 24px" }}>
            {loading ? <><Spinner size={15} /> Searching…</> : "⊕ Search Candidates"}
          </button>
          <button className="btn btn-ghost" onClick={() => setShowFilters((f) => !f)} style={{ padding: "10px 16px" }}>
            {showFilters ? "Hide Filters" : "⊞ Advanced Filters"}
          </button>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Show top</span>
            <select className="select" value={topK} onChange={(e) => setTopK(+e.target.value)} style={{ width: 72, padding: "7px 10px" }}>
              {[3, 5, 10, 20, 50].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
        </div>

        {showFilters && (
          <div className="anim-fadeup" style={{ marginTop: 18, paddingTop: 18, borderTop: "1px solid var(--border)", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div>
              <Label>Required Skills</Label>
              <input className="input" placeholder="Python, Django, PostgreSQL (comma-separated)" value={reqSkills} onChange={(e) => setReqSkills(e.target.value)} />
            </div>
            <div>
              <Label>Nice-to-Have Skills</Label>
              <input className="input" placeholder="Docker, Redis, TypeScript…" value={niceSkills} onChange={(e) => setNiceSkills(e.target.value)} />
            </div>
            <div>
              <Label>Minimum Experience (years)</Label>
              <input className="input" type="number" min="0" placeholder="e.g. 3" value={minExp} onChange={(e) => setMinExp(e.target.value)} />
            </div>
            <div>
              <Label>Ideal Experience (years)</Label>
              <input className="input" type="number" min="0" placeholder="e.g. 7" value={niceExp} onChange={(e) => setNiceExp(e.target.value)} />
            </div>
          </div>
        )}
      </SectionCard>

      {/* Results */}
      {searched && (
        <div className="anim-fadeup">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
            <div className="font-display" style={{ fontSize: 16, fontWeight: 700 }}>Results</div>
            <span className="tag tag-amber">{results?.length ?? 0} candidates</span>
          </div>

          {!results?.length ? (
            <EmptyState icon="⊕" title="No candidates found" body="Try broadening your query or uploading more resumes" />
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {results.map((r) => (
                <SectionCard key={r.resume_id} style={{ padding: 20 }} hover>
                  <div style={{ display: "grid", gridTemplateColumns: "56px 1fr auto", gap: 18, alignItems: "start" }}>
                    {/* Rank */}
                    <div style={{ textAlign: "center", paddingTop: 4 }}>
                      <div className="rank-badge font-display" style={{ color: rankColor(r.rank) }}>
                        #{r.rank}
                      </div>
                    </div>

                    {/* Info */}
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
                        <div className="font-display" style={{ fontSize: 16, fontWeight: 800 }}>
                          {r.candidate_name || "Unknown Candidate"}
                        </div>
                        <RecommendationBadge recommendation={r.recommendation} />
                        {r.candidate_email && (
                          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>{r.candidate_email}</span>
                        )}
                        {r.experience_years && (
                          <span className="tag tag-violet font-mono">{r.experience_years}y exp</span>
                        )}
                      </div>

                      {/* Score breakdown */}
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 12 }}>
                        <ScoreBar value={r.semantic_similarity} label="Semantic" />
                        <ScoreBar value={r.experience_match} label="Experience" />
                        <ScoreBar value={r.skill_overlap} label="Skills" />
                      </div>

                      {/* Matched & Missing Skills */}
                      {(r.matched_skills?.length > 0 || r.missing_skills?.length > 0) && (
                        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                          {r.matched_skills?.length > 0 && (
                            <div>
                              <span className="field-label" style={{ fontSize: 10, marginRight: 6 }}>Matched:</span>
                              {r.matched_skills.map((s) => (
                                <span key={s} className="tag tag-emerald" style={{ fontSize: 11, marginRight: 4 }}>{s}</span>
                              ))}
                            </div>
                          )}
                          {r.missing_skills?.length > 0 && (
                            <div>
                              <span className="field-label" style={{ fontSize: 10, marginRight: 6 }}>Missing:</span>
                              {r.missing_skills.map((s) => (
                                <span key={s} className="tag tag-rose" style={{ fontSize: 11, marginRight: 4 }}>{s}</span>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Final score */}
                    <div style={{ textAlign: "center", padding: "10px 18px", background: "var(--surface)", borderRadius: 12, border: "1px solid var(--border)", flexShrink: 0 }}>
                      <div className="field-label" style={{ marginBottom: 4 }}>Score</div>
                      <div
                        className="font-display"
                        style={{
                          fontSize: 26, fontWeight: 900,
                          color: r.final_score >= 0.7 ? "var(--emerald)" : r.final_score >= 0.5 ? "var(--amber)" : "var(--rose)",
                        }}
                      >
                        {Math.round(r.final_score * 100)}
                      </div>
                    </div>
                  </div>
                </SectionCard>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
