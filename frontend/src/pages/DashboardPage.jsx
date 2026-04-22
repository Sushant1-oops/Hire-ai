import { useEffect, useState } from "react";
import { resumeApi, healthApi } from "../api";
import { useAuth } from "../context/AuthContext";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import EmptyState from "../components/EmptyState";

function StatCard({ label, value, color, icon }) {
  return (
    <div className="card card-glow" style={{ padding: "20px 22px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div className="stat-label">{label}</div>
        <span style={{ fontSize: 22, color }}>{icon}</span>
      </div>
      <div className="stat-value" style={{ color }}>{value}</div>
    </div>
  );
}

function SkeletonBlock({ height = 80 }) {
  return <div className="skeleton" style={{ height, borderRadius: 12 }} />;
}

export default function DashboardPage() {
  const { token, user } = useAuth();
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([resumeApi.stats(token), healthApi.check()]).then(
      ([s, h]) => {
        if (s.data) setStats(s.data);
        setHealth(h);
        setLoading(false);
      }
    );
  }, [token]);

  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  if (loading) {
    return (
      <div className="anim-fadeup" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <SkeletonBlock height={60} />
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14 }}>
          {[...Array(4)].map((_, i) => <SkeletonBlock key={i} height={100} />)}
        </div>
        <SkeletonBlock height={300} />
      </div>
    );
  }

  return (
    <div className="anim-fadeup">
      <PageHeader
        title={`${greeting}, ${user?.username || "Recruiter"} 👋`}
        subtitle="Your hiring overview at a glance"
      />

      {/* Health Status */}
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 10,
          padding: "9px 16px",
          background: "var(--card)",
          border: "1px solid var(--border)",
          borderRadius: 10,
          marginBottom: 26,
        }}
      >
        <span
          className="pulse-dot"
          style={{
            background:
              health?.status === "healthy" ? "var(--emerald)" : "var(--rose)",
          }}
        />
        <span className="font-mono" style={{ fontSize: 11.5, color: "var(--text-muted)" }}>
          API:{" "}
          <span style={{ color: health?.status === "healthy" ? "var(--emerald)" : "var(--rose)" }}>
            {health?.status ?? "unknown"}
          </span>
          &nbsp;·&nbsp;Ollama:{" "}
          <span
            style={{
              color:
                health?.ollama === "connected"
                  ? "var(--emerald)"
                  : "var(--amber)",
            }}
          >
            {health?.ollama ?? "unknown"}
          </span>
        </span>
      </div>

      {/* Stat cards */}
      <div
        className="anim-stagger"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 14,
          marginBottom: 26,
        }}
      >
        {[
          { label: "Total Resumes",   value: stats?.total_resumes ?? 0,          color: "var(--amber)",   icon: "⊟" },
          { label: "Avg Experience",  value: `${stats?.avg_experience ?? 0}y`,    color: "var(--violet)",  icon: "◎" },
          { label: "Unique Skills",   value: stats?.top_skills?.length ?? 0,      color: "var(--emerald)", icon: "⊕" },
          { label: "Recent Searches", value: stats?.recent_searches?.length ?? 0, color: "var(--cyan)",    icon: "⊛" },
        ].map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      {/* Bottom grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}>
        {/* Top skills */}
        <SectionCard>
          <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--border)" }}>
            <div className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
              Top Skills in Pool
            </div>
          </div>
          <div style={{ padding: 16 }}>
            {stats?.top_skills?.length ? (
              stats.top_skills.slice(0, 8).map((s, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 11 }}>
                  <span className="font-mono" style={{ fontSize: 10, color: "var(--text-muted)", minWidth: 18 }}>
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 13, color: "var(--text)" }}>{s.skill}</span>
                      <span className="font-mono" style={{ fontSize: 11, color: "var(--amber)" }}>{s.count}</span>
                    </div>
                    <div className="score-track">
                      <div
                        className="score-fill"
                        style={{
                          width: `${(s.count / (stats.top_skills[0]?.count || 1)) * 100}%`,
                          background: "var(--amber)",
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState icon="⊟" title="No data yet" body="Upload resumes to see skill distribution" />
            )}
          </div>
        </SectionCard>

        {/* Recent searches */}
        <SectionCard>
          <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--border)" }}>
            <div className="font-display" style={{ fontSize: 14, fontWeight: 700 }}>
              Recent Searches
            </div>
          </div>
          <div style={{ padding: 10 }}>
            {stats?.recent_searches?.length ? (
              stats.recent_searches.map((s, i) => (
                <div
                  key={i}
                  style={{
                    padding: "10px 12px",
                    borderRadius: 9,
                    marginBottom: 6,
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                  }}
                >
                  <div
                    style={{
                      fontSize: 13,
                      color: "var(--text)",
                      marginBottom: 5,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {s.query}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="tag tag-amber">{s.results_count} results</span>
                    <span className="font-mono" style={{ fontSize: 10, color: "var(--text-muted)" }}>
                      {new Date(s.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <EmptyState icon="⊕" title="No searches yet" body="Run a semantic search to see history here" />
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
