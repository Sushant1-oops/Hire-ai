import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { authApi } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import Spinner from "../components/Spinner";
import Label from "../components/Label";

export default function LoginPage() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!email || !password) return toast("Email and password required", "error");
    setLoading(true);
    const res = await authApi.login(email, password);
    setLoading(false);
    if (res.error || !res.data) return toast(res.message || "Login failed", "error");
    toast("Welcome back!", "success");
    login(res.data.access_token, res.data.user);
    navigate("/");
  }

  const onKey = (e) => e.key === "Enter" && handleLogin();

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg)",
        padding: 20,
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Background glows */}
      <div style={{ position: "fixed", top: "8%", right: "14%", width: 360, height: 360, background: "radial-gradient(circle, rgba(245,158,11,0.06) 0%, transparent 65%)", pointerEvents: "none" }} />
      <div style={{ position: "fixed", bottom: "15%", left: "8%", width: 280, height: 280, background: "radial-gradient(circle, rgba(129,140,248,0.05) 0%, transparent 65%)", pointerEvents: "none" }} />
      <div style={{ position: "fixed", top: "50%", left: "50%", width: 500, height: 500, background: "radial-gradient(circle, rgba(16,185,129,0.025) 0%, transparent 65%)", transform: "translate(-50%,-50%)", pointerEvents: "none" }} />

      <div className="anim-fadeup" style={{ width: "100%", maxWidth: 420 }}>
        {/* Brand */}
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div
            className="font-display"
            style={{ fontSize: 30, fontWeight: 900, color: "var(--amber)", letterSpacing: "-0.02em", marginBottom: 10 }}
          >
            ◆ HireAI
          </div>
          <div className="font-display" style={{ fontSize: 20, fontWeight: 700, color: "var(--text)", marginBottom: 6 }}>
            Sign in to your account
          </div>
          <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>
            AI-powered semantic hiring platform
          </div>
        </div>

        {/* Form card */}
        <div
          style={{
            background: "var(--card)",
            border: "1px solid var(--border2)",
            borderRadius: 16,
            padding: 30,
          }}
        >
          <div style={{ marginBottom: 18 }}>
            <Label htmlFor="email">Email Address</Label>
            <input
              id="email"
              className="input"
              type="email"
              placeholder="recruiter@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={onKey}
            />
          </div>
          <div style={{ marginBottom: 26 }}>
            <Label htmlFor="password">Password</Label>
            <input
              id="password"
              className="input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={onKey}
            />
          </div>
          <button
            className="btn btn-primary"
            onClick={handleLogin}
            disabled={loading}
            style={{ width: "100%", padding: "13px", fontSize: 15 }}
          >
            {loading ? <><Spinner size={16} /> Signing in…</> : "Sign In →"}
          </button>
        </div>

        <div style={{ textAlign: "center", marginTop: 18, fontSize: 13.5, color: "var(--text-muted)" }}>
          Don&apos;t have an account?{" "}
          <Link to="/register" style={{ color: "var(--amber)", fontWeight: 600, textDecoration: "none" }}>
            Create one
          </Link>
        </div>
      </div>
    </div>
  );
}
