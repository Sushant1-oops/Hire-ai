import { Routes, Route, Navigate, Outlet } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";

import Sidebar from "./components/Sidebar";

import LoginPage      from "./pages/LoginPage";
import RegisterPage   from "./pages/RegisterPage";
import DashboardPage  from "./pages/DashboardPage";
import ResumesPage    from "./pages/ResumesPage";
import SearchPage     from "./pages/SearchPage";
import AIMatchPage    from "./pages/AIMatchPage";
import InterviewQPage from "./pages/InterviewQPage";
import OutreachEmailPage from "./pages/OutreachEmailPage";
import JobDescPage    from "./pages/JobDescPage";

// ─── Protected Layout ─────────────────────────────────────────
function AppLayout() {
  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar />
      <main
        style={{
          marginLeft: 224,
          flex: 1,
          padding: "34px 38px",
          background: "var(--bg)",
          minHeight: "100vh",
        }}
      >
        <Outlet />
      </main>
    </div>
  );
}

// ─── Auth Guard ───────────────────────────────────────────────
function RequireAuth() {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <AppLayout />;
}

function RedirectIfAuthed() {
  const { token } = useAuth();
  if (token) return <Navigate to="/" replace />;
  return <Outlet />;
}

// ─── Routes ───────────────────────────────────────────────────
function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route element={<RedirectIfAuthed />}>
        <Route path="/login"    element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* Protected routes */}
      <Route element={<RequireAuth />}>
        <Route path="/"              element={<DashboardPage />} />
        <Route path="/resumes"       element={<ResumesPage />} />
        <Route path="/search"        element={<SearchPage />} />
        <Route path="/ai-match"      element={<AIMatchPage />} />
        <Route path="/ai-questions"  element={<InterviewQPage />} />
        <Route path="/ai-email"      element={<OutreachEmailPage />} />
        <Route path="/ai-jd"         element={<JobDescPage />} />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

// ─── Root App ─────────────────────────────────────────────────
export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <AppRoutes />
      </ToastProvider>
    </AuthProvider>
  );
}
