import { Link, useRouterState, useNavigate } from "@tanstack/react-router";
import { motion } from "motion/react";
import { LayoutDashboard, FileText, Search, Briefcase, LogOut, Sparkles, Menu } from "lucide-react";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/resumes", label: "Resumes", icon: FileText },
  { to: "/search", label: "Semantic Search", icon: Search },
  { to: "/jobs", label: "Jobs", icon: Briefcase },
] as const;

export function AppShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  const sidebar = (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="flex items-center gap-2 px-6 py-6">
        <span className="flex size-9 items-center justify-center rounded-xl bg-sidebar-primary">
          <Sparkles className="size-5 text-sidebar-primary-foreground" />
        </span>
        <div>
          <p className="text-sm font-semibold tracking-tight">HireAI</p>
          <p className="text-xs text-sidebar-foreground/60">Semantic hiring</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {NAV.map((item) => {
          const active = pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={() => setOpen(false)}
              className={cn(
                "relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                active
                  ? "text-sidebar-accent-foreground"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-active"
                  className="absolute inset-0 rounded-lg bg-sidebar-accent"
                  transition={{ type: "spring", stiffness: 400, damping: 32 }}
                />
              )}
              <item.icon className="relative size-4" />
              <span className="relative">{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-sidebar-border p-4">
        <p className="truncate text-sm font-medium">{user?.full_name ?? user?.email}</p>
        <p className="truncate text-xs text-sidebar-foreground/60">
          {user?.company ?? "Recruiter"}
        </p>
        <button
          onClick={() => {
            logout();
            navigate({ to: "/login", replace: true });
          }}
          className="mt-3 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-sm text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground"
        >
          <LogOut className="size-4" /> Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-background">
      <aside className="hidden w-64 shrink-0 lg:block">
        <div className="fixed inset-y-0 w-64">{sidebar}</div>
      </aside>

      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-foreground/40" onClick={() => setOpen(false)} />
          <motion.div
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            className="absolute inset-y-0 left-0 w-64"
          >
            {sidebar}
          </motion.div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-background/80 px-5 py-4 backdrop-blur lg:px-8">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="size-5" />
          </Button>
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold tracking-tight">{title}</h1>
            {description && <p className="truncate text-sm text-muted-foreground">{description}</p>}
          </div>
        </header>
        <motion.main
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className="flex-1 px-5 py-6 lg:px-8"
        >
          {children}
        </motion.main>
      </div>
    </div>
  );
}
