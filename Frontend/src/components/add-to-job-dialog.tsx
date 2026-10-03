import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { addCandidateToJob, jobsQuery } from "@/lib/queries";

/** Pick one of your jobs to add a library candidate to (shows up as a "manual" application). */
export function AddToJobDialog({
  resumeId,
  candidateName,
  onOpenChange,
}: {
  resumeId: number | null;
  candidateName?: string | null | undefined;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ ...jobsQuery(), enabled: resumeId !== null });
  const [pendingJob, setPendingJob] = useState<number | null>(null);
  const jobs = data ?? [];

  const add = useMutation({
    mutationFn: (jobId: number) => addCandidateToJob(jobId, resumeId!),
    onMutate: (jobId) => setPendingJob(jobId),
    onSuccess: () => {
      toast.success("Candidate added — scoring in progress");
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["resumes"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      onOpenChange(false);
    },
    onError: (e: Error) => toast.error(e.message),
    onSettled: () => setPendingJob(null),
  });

  return (
    <Dialog open={resumeId !== null} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add to a job</DialogTitle>
          <DialogDescription>
            {candidateName?.trim() || "This candidate"} will be scored against the job you pick.
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-80 space-y-2 overflow-y-auto">
          {isLoading && <p className="text-sm text-muted-foreground">Loading jobs…</p>}
          {!isLoading && !jobs.length && (
            <p className="text-sm text-muted-foreground">Create a job first, then add candidates to it.</p>
          )}
          {jobs.map((job) => (
            <div
              key={job.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-border p-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{job.title}</p>
                <p className="text-xs text-muted-foreground">
                  {job.application_count ?? 0} applicants
                  {job.status === "closed" && (
                    <Badge variant="secondary" className="ml-2">
                      closed
                    </Badge>
                  )}
                </p>
              </div>
              <Button
                size="sm"
                variant="secondary"
                disabled={add.isPending}
                onClick={() => add.mutate(job.id)}
              >
                {pendingJob === job.id ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <Plus className="size-3.5" />
                )}
                Add
              </Button>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
