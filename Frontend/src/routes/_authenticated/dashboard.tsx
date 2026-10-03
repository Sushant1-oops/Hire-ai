import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  AlertTriangle,
  ArrowRight,
  Briefcase,
  CheckCircle2,
  Inbox,
  Loader2,
  UserCheck,
  Users,
} from "lucide-react";
import type { ComponentType } from "react";
import { AppShell } from "@/components/app-shell";
import { RecommendationBadge } from "@/components/recommendation-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardStatsQuery } from "@/lib/queries";
import { cn } from "@/lib/utils";
import type { ApplicationStatus } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — HireAI" },
      {
        name: "description",
        content: "Your hiring pipeline, candidates awaiting a decision and jobs that need attention.",
      },
    ],
  }),
  component: DashboardPage,
});

const STATUS_LABEL: Record<ApplicationStatus, string> = {
  received: "New",
  screened: "Screened",
  shortlisted: "Shortlisted",
  interview: "Interview",
  hired: "Hired",
  rejected: "Rejected",
};

function Kpi({
  label,
  value,
  hint,
  icon: Icon,
  loading,
  index,
}: {
  label: string;
  value: number | undefined;
  hint: string;
  icon: ComponentType<{ className?: string }>;
  loading: boolean;
  index: number;
}) {
  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.06 }}>
      <Card className="shadow-soft">
        <CardContent className="flex items-center justify-between pt-6">
          <div>
            <p className="text-sm text-muted-foreground">{label}</p>
            {loading ? (
              <Skeleton className="mt-2 h-7 w-16" />
            ) : (
              <p className="mt-1 text-2xl font-semibold tracking-tight">{value ?? 0}</p>
            )}
            <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
          </div>
          <span className="flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
            <Icon className="size-5" />
          </span>
        </CardContent>
      </Card>
    </motion.div>
  );
}

function DashboardPage() {
  const { data, isLoading, error } = useQuery({ ...dashboardStatsQuery(), refetchInterval: 30_000 });
  const kpis = data?.kpis;
  const library = data?.library;
  const attention = (library?.failed ?? 0) + (library?.needs_review ?? 0) + (library?.processing ?? 0);
  const funnelMax = Math.max(1, ...(data?.pipeline ?? []).map((p) => p.count));

  return (
    <AppShell title="Dashboard" description="What needs your attention today">
      {error && (
        <p className="mb-6 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {(error as Error).message}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi index={0} loading={isLoading} icon={Briefcase} label="Open jobs" value={kpis?.open_jobs} hint="Accepting applications" />
        <Kpi index={1} loading={isLoading} icon={Inbox} label="Awaiting decision" value={kpis?.awaiting_decision} hint="New or screened, not yet decided" />
        <Kpi index={2} loading={isLoading} icon={UserCheck} label="In progress" value={kpis?.in_interview_stage} hint="Shortlisted or interviewing" />
        <Kpi index={3} loading={isLoading} icon={Users} label="Hired" value={kpis?.hired} hint={`${kpis?.total_applications ?? 0} applications in total`} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-5">
        <Card className="shadow-soft lg:col-span-3">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Candidates to review first</CardTitle>
            <span className="text-xs text-muted-foreground">Best matches not yet decided</span>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading && <Skeleton className="h-40 w-full" />}
            {(data?.top_candidates ?? []).map((c) => (
              <Link
                key={c.application_id}
                to="/jobs/$jobId"
                params={{ jobId: String(c.job_id) }}
                className="flex items-center gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent/40"
              >
                <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                  {Math.round(c.score * 100)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{c.candidate_name ?? "Unnamed candidate"}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {c.job_title} · {STATUS_LABEL[c.status]}
                  </p>
                </div>
                <RecommendationBadge value={c.recommendation} />
                <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
              </Link>
            ))}
            {!isLoading && !data?.top_candidates.length && (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Nobody is waiting on you. Strong new applicants will appear here.
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="shadow-soft lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Hiring pipeline</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading && <Skeleton className="h-40 w-full" />}
            {(data?.pipeline ?? []).map((stage) => (
              <div key={stage.status} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{STATUS_LABEL[stage.status]}</span>
                  <span className="font-medium">{stage.count}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-secondary">
                  <motion.div
                    className={cn("h-full rounded-full", stage.status === "rejected" ? "bg-muted-foreground/40" : stage.status === "hired" ? "bg-success" : "bg-primary")}
                    initial={{ width: 0 }}
                    animate={{ width: `${(stage.count / funnelMax) * 100}%` }}
                    transition={{ duration: 0.6, ease: "easeOut" }}
                  />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card className="shadow-soft lg:col-span-3">
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle className="text-base">Open jobs</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link to="/jobs">All jobs</Link>
            </Button>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading && <Skeleton className="h-32 w-full" />}
            {(data?.jobs ?? []).map((job) => (
              <Link
                key={job.id}
                to="/jobs/$jobId"
                params={{ jobId: String(job.id) }}
                className="flex items-center justify-between gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-accent/40"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{job.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {job.applicants} applicant{job.applicants === 1 ? "" : "s"} · {job.in_pipeline} in progress
                    {job.top_score != null ? ` · best match ${Math.round(job.top_score * 100)}%` : ""}
                  </p>
                </div>
                {job.new > 0 && (
                  <span className="shrink-0 rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">
                    {job.new} new
                  </span>
                )}
              </Link>
            ))}
            {!isLoading && !data?.jobs.length && (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No open jobs. <Link to="/jobs" className="font-medium text-primary hover:underline">Create one</Link> to start receiving applications.
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="shadow-soft lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Resume library</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {isLoading && <Skeleton className="h-24 w-full" />}
            {!isLoading && (
              <>
                <p className="text-muted-foreground">
                  {kpis?.library_size ?? 0} resume{kpis?.library_size === 1 ? "" : "s"} searchable.
                </p>
                {attention === 0 ? (
                  <p className="flex items-center gap-2 text-success">
                    <CheckCircle2 className="size-4" /> Everything parsed cleanly.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {!!library?.failed && (
                      <li className="flex items-center gap-2 text-destructive">
                        <AlertTriangle className="size-4" /> {library.failed} could not be processed
                      </li>
                    )}
                    {!!library?.needs_review && (
                      <li className="flex items-center gap-2">
                        <AlertTriangle className="size-4 text-warning" /> {library.needs_review} need their name or email checked
                      </li>
                    )}
                    {!!library?.processing && (
                      <li className="flex items-center gap-2 text-muted-foreground">
                        <Loader2 className="size-4 animate-spin" /> {library.processing} still processing
                      </li>
                    )}
                  </ul>
                )}
                <Button asChild variant="outline" size="sm">
                  <Link to="/resumes">Open library</Link>
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
