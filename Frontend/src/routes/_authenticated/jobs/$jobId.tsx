import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  ChevronDown,
  ChevronRight,
  Copy,
  FileText,
  Loader2,
  Lock,
  LockOpen,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { AiHub, type AiHubTarget } from "@/components/ai-hub";
import { CandidateDrawer } from "@/components/candidate-drawer";
import { JobFormDialog } from "@/components/job-form-dialog";
import { RecommendationBadge } from "@/components/recommendation-badge";
import { MetricBar } from "@/components/score-ring";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  addCandidateToJob,
  deleteJob,
  jobApplicationsQuery,
  openResumeFile,
  removeApplication,
  resumesQuery,
  setApplicationStatus,
  setJobStatus,
} from "@/lib/queries";
import type { ApplicationStatus, Job, RankedApplication } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/jobs/$jobId")({
  head: ({ params }) => ({
    meta: [{ title: `Job ${params.jobId} — HireAI` }],
  }),
  component: JobDetailPage,
});

const STATUSES: ApplicationStatus[] = ["received", "screened", "shortlisted", "interview", "hired", "rejected"];
const STATUS_LABEL: Record<ApplicationStatus, string> = {
  received: "New",
  screened: "Screened",
  shortlisted: "Shortlisted",
  interview: "Interview",
  hired: "Hired",
  rejected: "Rejected",
};

type Data = { job: Job; applications: RankedApplication[] };

function JobDetailPage() {
  const { jobId } = Route.useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const queryKey = ["jobs", jobId, "applications"];

  const { data, isLoading, error } = useQuery({
    ...jobApplicationsQuery(jobId),
    // Applications are parsed and scored in the background: keep refreshing while any are pending.
    refetchInterval: (query) =>
      (query.state.data?.applications ?? []).some((a) => a.processing_status === "pending") ? 4000 : false,
  });
  const applications = data?.applications ?? [];
  const job = data?.job;

  const [filter, setFilter] = useState<ApplicationStatus | "all">("all");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [adding, setAdding] = useState(false);
  const [candidate, setCandidate] = useState<number | null>(null);
  const [aiTarget, setAiTarget] = useState<AiHubTarget | null>(null);
  const [toRemove, setToRemove] = useState<RankedApplication | null>(null);

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: applications.length };
    for (const a of applications) c[a.status] = (c[a.status] ?? 0) + 1;
    return c;
  }, [applications]);
  const visible = filter === "all" ? applications : applications.filter((a) => a.status === filter);

  const refreshAll = () => {
    queryClient.invalidateQueries({ queryKey: ["jobs"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  // Optimistic: the dropdown feels instant and rolls back if the request fails.
  const statusMutation = useMutation({
    mutationFn: ({ applicationId, status }: { applicationId: number; status: ApplicationStatus }) =>
      setApplicationStatus(applicationId, status),
    onMutate: async ({ applicationId, status }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<Data>(queryKey);
      if (previous) {
        queryClient.setQueryData<Data>(queryKey, {
          ...previous,
          applications: previous.applications.map((a) => (a.application_id === applicationId ? { ...a, status } : a)),
        });
      }
      return { previous };
    },
    onError: (e: Error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(queryKey, context.previous);
      toast.error(e.message);
    },
    onSuccess: () => toast.success("Status updated"),
    onSettled: refreshAll,
  });

  const toggleStatus = useMutation({
    mutationFn: () => setJobStatus(jobId, job?.status === "open" ? "closed" : "open"),
    onSuccess: () => {
      toast.success(job?.status === "open" ? "Job closed — the apply link no longer accepts applications" : "Job reopened");
      refreshAll();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: () => deleteJob(jobId),
    onSuccess: () => {
      toast.success("Job deleted");
      queryClient.removeQueries({ queryKey: ["jobs", jobId] });
      refreshAll();
      navigate({ to: "/jobs", replace: true });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const dropApplication = useMutation({
    mutationFn: (applicationId: number) => removeApplication(applicationId),
    onSuccess: () => {
      toast.success("Removed from this job");
      setToRemove(null);
      refreshAll();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const copyLink = async () => {
    if (!job) return;
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/apply/${job.public_slug}`);
      toast.success("Apply link copied");
    } catch {
      toast.error("Could not copy the link");
    }
  };

  return (
    <AppShell
      title={job?.title ?? "Job"}
      description={job ? `${job.location ?? "Location not set"} · ${applications.length} applicant${applications.length === 1 ? "" : "s"}` : "Loading job details"}
    >
      {job && (
        <div className="mb-6 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={job.status === "open" ? "default" : "secondary"}>{job.status}</Badge>
            {job.experience_min ? <Badge variant="outline">{job.experience_min}+ yrs</Badge> : null}
            {(job.required_skills ?? []).map((s) => (
              <Badge key={s} variant="secondary">
                {s}
              </Badge>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={copyLink}>
              <Copy className="size-3.5" /> Copy apply link
            </Button>
            <Button variant="outline" size="sm" onClick={() => setAdding(true)}>
              <Plus className="size-3.5" /> Add from library
            </Button>
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Pencil className="size-3.5" /> Edit
            </Button>
            <Button variant="outline" size="sm" disabled={toggleStatus.isPending} onClick={() => toggleStatus.mutate()}>
              {job.status === "open" ? <Lock className="size-3.5" /> : <LockOpen className="size-3.5" />}
              {job.status === "open" ? "Close job" : "Reopen job"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="text-destructive hover:text-destructive"
              onClick={() => setConfirmDelete(true)}
            >
              <Trash2 className="size-3.5" /> Delete
            </Button>
          </div>
        </div>
      )}

      {error && (
        <p className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {(error as Error).message}
        </p>
      )}

      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      )}

      {!isLoading && !!applications.length && (
        <>
          <div className="mb-3 flex flex-wrap gap-2">
            {(["all", ...STATUSES] as const).map((key) =>
              key === "all" || (counts[key] ?? 0) > 0 || filter === key ? (
                <Button key={key} size="sm" variant={filter === key ? "default" : "outline"} onClick={() => setFilter(key)}>
                  {key === "all" ? "All" : STATUS_LABEL[key]} <span className="ml-1 opacity-70">{counts[key] ?? 0}</span>
                </Button>
              ) : null,
            )}
          </div>

          <div className="overflow-x-auto rounded-xl border border-border shadow-soft">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-10" />
                  <TableHead className="w-14">Rank</TableHead>
                  <TableHead>Candidate</TableHead>
                  <TableHead>Match</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-28 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visible.map((app) => {
                  const open = expanded === app.application_id;
                  const ready = app.processing_status === "ready";
                  return (
                    <Fragment key={app.application_id}>
                      <TableRow>
                        <TableCell>
                          {ready && (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="size-7"
                              aria-label={open ? "Hide score details" : "Show score details"}
                              onClick={() => setExpanded(open ? null : app.application_id)}
                            >
                              {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                            </Button>
                          )}
                        </TableCell>
                        <TableCell className="font-medium">{app.rank != null ? `#${app.rank}` : "—"}</TableCell>
                        <TableCell>
                          <button
                            className="text-left font-medium hover:underline"
                            onClick={() => setCandidate(app.resume_id)}
                          >
                            {app.candidate_name ?? "Unnamed candidate"}
                          </button>
                          <p className="text-xs text-muted-foreground">
                            {app.candidate_email ?? "No email"}
                            {app.experience_years != null ? ` · ${app.experience_years} yrs` : ""}
                          </p>
                        </TableCell>
                        <TableCell>
                          {app.processing_status === "pending" && (
                            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                              <Loader2 className="size-3 animate-spin" /> Processing…
                            </span>
                          )}
                          {app.processing_status === "failed" && (
                            <span className="text-xs text-destructive" title={app.processing_error ?? undefined}>
                              Failed to process
                            </span>
                          )}
                          {ready && (
                            <div className="flex items-center gap-2">
                              <Badge variant="secondary">{Math.round(app.final_score * 100)}%</Badge>
                              <RecommendationBadge value={app.recommendation} />
                            </div>
                          )}
                        </TableCell>
                        <TableCell className="text-sm capitalize text-muted-foreground">{app.source}</TableCell>
                        <TableCell>
                          <Select
                            value={app.status}
                            onValueChange={(status) =>
                              statusMutation.mutate({ applicationId: app.application_id, status: status as ApplicationStatus })
                            }
                          >
                            <SelectTrigger className="h-8 w-36">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {STATUSES.map((s) => (
                                <SelectItem key={s} value={s}>
                                  {STATUS_LABEL[s]}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="size-8"
                              title="AI Hub for this job"
                              disabled={!ready}
                              onClick={() =>
                                setAiTarget({
                                  resumeId: app.resume_id,
                                  name: app.candidate_name,
                                  email: app.candidate_email,
                                  jobId: job?.id,
                                })
                              }
                            >
                              <Sparkles className="size-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="size-8"
                              title="Open original PDF"
                              onClick={() => openResumeFile(app.resume_id).catch((e: Error) => toast.error(e.message))}
                            >
                              <FileText className="size-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="size-8 text-muted-foreground hover:text-destructive"
                              title="Remove from this job"
                              onClick={() => setToRemove(app)}
                            >
                              <X className="size-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                      {open && ready && (
                        <TableRow className="bg-muted/40 hover:bg-muted/40">
                          <TableCell />
                          <TableCell colSpan={6}>
                            <div className="grid gap-4 py-2 md:grid-cols-2">
                              <div className="space-y-2">
                                <MetricBar label="Semantic fit" value={app.semantic_similarity} />
                                <MetricBar label="Skills" value={app.skill_overlap} />
                                <MetricBar label="Experience" value={app.experience_match} />
                              </div>
                              <div className="space-y-2 text-sm">
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span className="w-20 text-xs text-muted-foreground">Matched</span>
                                  {app.matched_skills.length ? (
                                    app.matched_skills.map((s) => (
                                      <Badge key={s} variant="outline" className="border-success/40 bg-success/10 text-success">
                                        ✓ {s}
                                      </Badge>
                                    ))
                                  ) : (
                                    <span className="text-xs text-muted-foreground">none</span>
                                  )}
                                </div>
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <span className="w-20 text-xs text-muted-foreground">Missing</span>
                                  {app.missing_skills.length ? (
                                    app.missing_skills.map((s) => (
                                      <Badge key={s} variant="outline" className="border-destructive/30 text-destructive">
                                        ✗ {s}
                                      </Badge>
                                    ))
                                  ) : (
                                    <span className="text-xs text-muted-foreground">none</span>
                                  )}
                                </div>
                                <Button variant="ghost" size="sm" className="-ml-2" onClick={() => setCandidate(app.resume_id)}>
                                  <UserRound className="size-3.5" /> Open candidate profile
                                </Button>
                              </div>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
                {!visible.length && (
                  <TableRow>
                    <TableCell colSpan={7} className="py-8 text-center text-sm text-muted-foreground">
                      No applicants in this stage.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </>
      )}

      {!isLoading && !applications.length && !error && (
        <p className="text-sm text-muted-foreground">
          No applications yet — share the apply link, or add candidates from your library.
        </p>
      )}

      <JobFormDialog open={editing} onOpenChange={setEditing} job={job} />
      <CandidateDrawer
        resumeId={candidate}
        onOpenChange={(open) => !open && setCandidate(null)}
        onOpenAiHub={(t) => setAiTarget({ resumeId: t.id, name: t.candidate_name, email: t.candidate_email, jobId: job?.id })}
      />
      <AiHub target={aiTarget} onOpenChange={(open) => !open && setAiTarget(null)} />
      <AddFromLibraryDialog
        open={adding}
        onOpenChange={setAdding}
        jobId={jobId}
        existing={new Set(applications.map((a) => a.resume_id))}
        onAdded={refreshAll}
      />

      <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete “{job?.title}”?</AlertDialogTitle>
            <AlertDialogDescription>
              The job, its apply link and all {applications.length} application record(s) are removed. The
              candidates’ resumes stay in your library. This can’t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={remove.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={remove.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault();
                remove.mutate();
              }}
            >
              {remove.isPending ? <Loader2 className="size-4 animate-spin" /> : null} Delete job
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!toRemove} onOpenChange={(o) => !o && setToRemove(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove from this job?</AlertDialogTitle>
            <AlertDialogDescription>
              {toRemove?.candidate_name ?? "This candidate"} is removed from the applicant list. Their resume stays in your
              library.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={dropApplication.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={dropApplication.isPending}
              onClick={(e) => {
                e.preventDefault();
                if (toRemove) dropApplication.mutate(toRemove.application_id);
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  );
}

/** Pick library candidates that aren't in this job yet. */
function AddFromLibraryDialog({
  open,
  onOpenChange,
  jobId,
  existing,
  onAdded,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jobId: string;
  existing: Set<number>;
  onAdded: () => void;
}) {
  const { data, isLoading } = useQuery({ ...resumesQuery(), enabled: open });
  const [term, setTerm] = useState("");
  const [busy, setBusy] = useState<number | null>(null);

  const candidates = (data ?? []).filter((r) => {
    if (existing.has(r.id) || r.processing_status !== "ready") return false;
    const needle = term.trim().toLowerCase();
    return !needle || [r.candidate_name, r.candidate_email].join(" ").toLowerCase().includes(needle);
  });

  const add = useMutation({
    mutationFn: (resumeId: number) => addCandidateToJob(jobId, resumeId),
    onMutate: (resumeId) => setBusy(resumeId),
    onSuccess: () => {
      toast.success("Candidate added");
      onAdded();
    },
    onError: (e: Error) => toast.error(e.message),
    onSettled: () => setBusy(null),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add from your library</DialogTitle>
          <DialogDescription>Candidates are scored against this job as soon as they are added.</DialogDescription>
        </DialogHeader>
        <Input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Search by name or email" />
        <div className="max-h-72 space-y-2 overflow-y-auto">
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {!isLoading && !candidates.length && (
            <p className="text-sm text-muted-foreground">No other processed resumes to add.</p>
          )}
          {candidates.map((r) => (
            <div key={r.id} className="flex items-center justify-between gap-3 rounded-lg border border-border p-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{r.candidate_name ?? "Unnamed candidate"}</p>
                <p className="truncate text-xs text-muted-foreground">{r.candidate_email ?? "No email"}</p>
              </div>
              <Button size="sm" variant="secondary" disabled={add.isPending} onClick={() => add.mutate(r.id)}>
                {busy === r.id ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />} Add
              </Button>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
