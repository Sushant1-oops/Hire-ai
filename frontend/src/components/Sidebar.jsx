import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV_ITEMS = [
  { to: "/",            label: "Dashboard",       icon: "◈" },
  { to: "/resumes",     label: "Resumes",          icon: "⊟" },
  { to: "/search",      label: "Semantic Search",  icon: "⊕" },
  { to: "/ai-match",    label: "AI Match",         icon: "⊛" },
  { to: "/ai-questions",label: "Interview Qs",     icon: "⊞" },
  { to: "/ai-email",    label: "Outreach Email",   icon: "◎" },
  { to: "/ai-jd",       label: "Job Description",  icon: "⊡" },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <aside
      style={{
        width: 224,
        minHeight: "100vh",
        background: "var(--surface)",
        borderRight: "1px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        padding: "0 12px",
        position: "fixed",
        top: 0,
        left: 0,
        zIndex: 40,
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: "22px 6px 18px",
          borderBottom: "1px solid var(--border)",
          marginBottom: 10,
        }}
      >
        <div
          className="font-display"
          style={{
            fontSize: 18,
            fontWeight: 900,
            color: "var(--amber)",
            letterSpacing: "-0.02em",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          ◆ HireAI
        </div>
        <div
          className="font-mono"
          style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 3 }}
        >
          Semantic Hiring Platform
        </div>
      </div>

      {/* Navigation */}
      <nav
        style={{ flex: 1, display: "flex", flexDirection: "column", gap: 3 }}
      >
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `nav-item ${isActive ? "active" : ""}`
            }
            style={{ textDecoration: "none" }}
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* User section */}
      <div
        style={{
          padding: "12px 0 16px",
          borderTop: "1px solid var(--border)",
          marginTop: 10,
        }}
      >
        {user && (
          <div style={{ padding: "6px 12px", marginBottom: 6 }}>
            <div
              style={{ fontSize: 13, fontWeight: 600, color: "var(--text)" }}
            >
              {user.username || user.email?.split("@")[0]}
            </div>
            <div
              style={{
                fontSize: 11.5,
                color: "var(--text-muted)",
                marginTop: 1,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {user.email}
            </div>
          </div>
        )}
        <div
          className="nav-item"
          onClick={handleLogout}
          style={{ color: "var(--rose)", cursor: "pointer" }}
        >
          <span className="nav-icon">⏻</span>
          <span>Sign Out</span>
        </div>
      </div>
    </aside>
  );
}
