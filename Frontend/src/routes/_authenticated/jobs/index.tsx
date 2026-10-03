import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { motion } from "motion/react";
import { toast } from "sonner";
import { Briefcase, Copy, Plus } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { JobFormDialog } from "@/components/job-form-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { jobsQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/jobs/")({
  head: () => ({
    meta: [
      { title: "Jobs — HireAI" },
      { name: "description", content: "Create job postings and share a public application link." },
    ],
  }),
  component: JobsPage,
});

function JobsPage() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery(jobsQuery());
  const jobs = data ?? [];
  const [creating, setCreating] = useState(false);

  const copyLink = async (slug: string) => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/apply/${slug}`);
      toast.success("Apply link copied");
    } catch {
      toast.error("Could not copy — select the link from the job page instead");
    }
  };

  return (
    <AppShell title="Jobs" description="Create a job and share its public application link">
      <div className="flex justify-end">
        <Button onClick={() => setCreating(true)}>
          <Plus className="size-4" /> New job
        </Button>
      </div>
      <JobFormDialog
        open={creating}
        onOpenChange={setCreating}
        onSaved={(job) => navigate({ to: "/jobs/$jobId", params: { jobId: String(job.id) } })}
      />

      {error && (
        <p className="mt-6 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {(error as Error).message}
        </p>
      )}

      {isLoading && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full rounded-2xl" />
          ))}
        </div>
      )}

      {!isLoading && !!jobs.length && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {jobs.map((job, i) => (
            <motion.div
              key={job.id}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.05, 0.3) }}
            >
              <Card
                onClick={() => navigate({ to: "/jobs/$jobId", params: { jobId: String(job.id) } })}
                className="h-full cursor-pointer shadow-soft transition-shadow hover:shadow-lg"
              >
                <CardContent className="flex h-full flex-col gap-3 pt-6">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium">{job.title}</p>
                    <Badge variant={job.status === "open" ? "default" : "secondary"}>{job.status}</Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {job.location ?? "Location not set"}
                    {job.experience_min ? ` · ${job.experience_min}+ yrs` : ""}
                  </p>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                    <span className="font-medium">
                      {job.application_count ?? 0} applicant{job.application_count === 1 ? "" : "s"}
                    </span>
                    {!!job.new_count && <span className="text-primary">{job.new_count} new</span>}
                    {job.top_score != null && (
                      <span className="text-muted-foreground">best {Math.round(job.top_score * 100)}%</span>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-auto"
                    onClick={(e) => {
                      e.stopPropagation();
                      copyLink(job.public_slug);
                    }}
                  >
                    <Copy className="size-3.5" /> Copy apply link
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {!isLoading && !jobs.length && !error && (
        <div className="mt-10 flex flex-col items-center gap-3 text-center text-muted-foreground">
          <Briefcase className="size-8" />
          <p className="text-sm">No jobs yet — create one to get a shareable application link.</p>
        </div>
      )}
    </AppShell>
  );
}
