import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Copy } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { jobApplicationsQuery, setApplicationStatus } from "@/lib/queries";
import type { ApplicationStatus, Job, RankedApplication } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/jobs/$jobId")({
  head: ({ params }) => ({
    meta: [{ title: `Job ${params.jobId} — HireAI` }],
  }),
  component: JobDetailPage,
});

const STATUSES: ApplicationStatus[] = [
  "received",
  "screened",
  "shortlisted",
  "interview",
  "hired",
  "rejected",
];

function JobDetailPage() {
  const { jobId } = Route.useParams();
  const queryClient = useQueryClient();
  const queryKey = ["jobs", jobId, "applications"];
  const { data, isLoading, error } = useQuery({
    ...jobApplicationsQuery(jobId),
    
    
    
    refetchInterval: (query) => {
      const applications = query.state.data?.applications ?? [];
      return applications.some((a) => a.processing_status === "pending") ? 4000 : false;
    },
  });
  const applications = data?.applications ?? [];
  const job = data?.job;

  
  
  const statusMutation = useMutation({
    mutationFn: ({ applicationId, status }: { applicationId: number; status: ApplicationStatus }) =>
      setApplicationStatus(applicationId, status),
    onMutate: async ({ applicationId, status }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<{ job: Job; applications: RankedApplication[] }>(
        queryKey,
      );
      if (previous) {
        queryClient.setQueryData(queryKey, {
          ...previous,
          applications: previous.applications.map((a) =>
            a.application_id === applicationId ? { ...a, status } : a,
          ),
        });
      }
      return { previous };
    },
    onError: (e: Error, _vars, context) => {
      if (context?.previous) queryClient.setQueryData(queryKey, context.previous);
      toast.error(e.message);
    },
    onSuccess: () => toast.success("Status updated"),
    onSettled: () => queryClient.invalidateQueries({ queryKey }),
  });

  const copyLink = async () => {
    if (!job) return;
    await navigator.clipboard.writeText(`${window.location.origin}/apply/${job.public_slug}`);
    toast.success("Apply link copied");
  };

  return (
    <AppShell
      title={job?.title ?? "Job"}
      description={
        job
          ? `${job.location ?? "Remote"} · ${applications.length} applications`
          : "Loading job details"
      }
    >
      {job && (
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <Badge variant={job.status === "open" ? "default" : "secondary"}>{job.status}</Badge>
          {(job.required_skills ?? []).map((s) => (
            <Badge key={s} variant="secondary">
              {s}
            </Badge>
          ))}
          <Button variant="outline" size="sm" onClick={copyLink} className="ml-auto">
            <Copy className="size-3.5" /> Copy apply link
          </Button>
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
        <div className="overflow-x-auto rounded-xl border border-border shadow-soft">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">Rank</TableHead>
                <TableHead>Candidate</TableHead>
                <TableHead>Match</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {applications.map((app) => (
                <TableRow key={app.application_id}>
                  <TableCell className="font-medium">#{app.rank}</TableCell>
                  <TableCell>
                    <p className="font-medium">{app.candidate_name ?? "Unnamed candidate"}</p>
                    <p className="text-xs text-muted-foreground">
                      {app.candidate_email ?? "No email"} · {app.experience_years ?? 0} yrs
                    </p>
                  </TableCell>
                  <TableCell>
                    {app.processing_status === "pending" && (
                      <span className="text-xs text-muted-foreground">Processing…</span>
                    )}
                    {app.processing_status === "failed" && (
                      <span
                        className="text-xs text-destructive"
                        title={app.processing_error ?? undefined}
                      >
                        Failed to process
                      </span>
                    )}
                    {app.processing_status === "ready" && (
                      <>
                        <Badge variant="secondary">{Math.round(app.final_score * 100)}%</Badge>
                        <span className="ml-2 text-xs text-muted-foreground">
                          {app.recommendation}
                        </span>
                      </>
                    )}
                  </TableCell>
                  <TableCell className="capitalize text-sm text-muted-foreground">
                    {app.source}
                  </TableCell>
                  <TableCell>
                    <Select
                      value={app.status}
                      onValueChange={(status) =>
                        statusMutation.mutate({
                          applicationId: app.application_id,
                          status: status as ApplicationStatus,
                        })
                      }
                    >
                      <SelectTrigger className="h-8 w-36">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {STATUSES.map((s) => (
                          <SelectItem key={s} value={s} className="capitalize">
                            {s}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {!isLoading && !applications.length && !error && (
        <p className="text-sm text-muted-foreground">
          No applications yet — share the apply link to start receiving candidates.
        </p>
      )}
    </AppShell>
  );
}
