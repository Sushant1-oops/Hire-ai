import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { authApi } from "../api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import Spinner from "../components/Spinner";
import Label from "../components/Label";

export default function RegisterPage() {
  const { login } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [loading, setLoading] = useState(false);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  async function handleRegister() {
    if (!form.username || !form.email || !form.password)
      return toast("All fields are required", "error");
    if (form.password.length < 6)
      return toast("Password must be at least 6 characters", "error");

    setLoading(true);
    const res = await authApi.register(form.username, form.email, form.password);
    setLoading(false);

    if (res.error || !res.data) return toast(res.message || "Registration failed", "error");
    toast("Account created! Welcome to HireAI", "success");
    login(res.data.access_token, res.data.user);
    navigate("/");
  }

  const onKey = (e) => e.key === "Enter" && handleRegister();

  const fields = [
    { key: "username", label: "Username",      type: "text",     placeholder: "johndoe" },
    { key: "email",    label: "Email Address", type: "email",    placeholder: "you@company.com" },
    { key: "password", label: "Password",      type: "password", placeholder: "min. 6 characters" },
  ];

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
      <div style={{ position: "fixed", top: "12%", left: "18%", width: 320, height: 320, background: "radial-gradient(circle, rgba(16,185,129,0.05) 0%, transparent 65%)", pointerEvents: "none" }} />
      <div style={{ position: "fixed", bottom: "10%", right: "12%", width: 280, height: 280, background: "radial-gradient(circle, rgba(245,158,11,0.06) 0%, transparent 65%)", pointerEvents: "none" }} />

      <div className="anim-fadeup" style={{ width: "100%", maxWidth: 420 }}>
        {/* Brand */}
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div className="font-display" style={{ fontSize: 30, fontWeight: 900, color: "var(--amber)", letterSpacing: "-0.02em", marginBottom: 10 }}>
            ◆ HireAI
          </div>
          <div className="font-display" style={{ fontSize: 20, fontWeight: 700, color: "var(--text)", marginBottom: 6 }}>
            Create your account
          </div>
          <div style={{ fontSize: 13.5, color: "var(--text-muted)" }}>
            Start hiring smarter with AI
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
          {fields.map(({ key, label, type, placeholder }) => (
            <div key={key} style={{ marginBottom: 18 }}>
              <Label htmlFor={key}>{label}</Label>
              <input
                id={key}
                className="input"
                type={type}
                placeholder={placeholder}
                value={form[key]}
                onChange={set(key)}
                onKeyDown={onKey}
              />
            </div>
          ))}

          <button
            className="btn btn-primary"
            onClick={handleRegister}
            disabled={loading}
            style={{ width: "100%", padding: "13px", fontSize: 15, marginTop: 8 }}
          >
            {loading ? <><Spinner size={16} /> Creating account…</> : "Create Account →"}
          </button>
        </div>

        <div style={{ textAlign: "center", marginTop: 18, fontSize: 13.5, color: "var(--text-muted)" }}>
          Already have an account?{" "}
          <Link to="/login" style={{ color: "var(--amber)", fontWeight: 600, textDecoration: "none" }}>
            Sign in
          </Link>
        </div>
      </div>
    </div>
  );
}
