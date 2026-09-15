import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { motion } from "motion/react";
import { toast } from "sonner";
import { Briefcase, Copy, Plus, Loader2 } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import { createJob, jobsQuery } from "@/lib/queries";

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
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery(jobsQuery());
  const jobs = data ?? [];
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [location, setLocation] = useState("");
  const [experienceMin, setExperienceMin] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState("");

  const create = useMutation({
    mutationFn: createJob,
    onSuccess: () => {
      toast.success("Job created — share the apply link with candidates");
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      setOpen(false);
      setTitle("");
      setLocation("");
      setExperienceMin("");
      setDescription("");
      setSkills("");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const applyUrl = (slug: string) => `${window.location.origin}/apply/${slug}`;

  const copyLink = async (slug: string) => {
    await navigator.clipboard.writeText(applyUrl(slug));
    toast.success("Apply link copied");
  };

  return (
    <AppShell title="Jobs" description="Create a job and share its public application link">
      <div className="flex justify-end">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="size-4" /> New job
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Create a job posting</DialogTitle>
              <DialogDescription>
                HireAI generates a public apply link — candidates don't need an account.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="job-title">Job title</Label>
                  <Input id="job-title" value={title} onChange={(e) => setTitle(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="job-location">Location</Label>
                  <Input
                    id="job-location"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="job-experience">Minimum experience (years)</Label>
                <Input
                  id="job-experience"
                  type="number"
                  min={0}
                  value={experienceMin}
                  onChange={(e) => setExperienceMin(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="job-skills">Required skills (comma separated)</Label>
                <Input
                  id="job-skills"
                  value={skills}
                  onChange={(e) => setSkills(e.target.value)}
                  placeholder="Python, FastAPI, PostgreSQL"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="job-description">Job description</Label>
                <Textarea
                  id="job-description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="min-h-32"
                />
              </div>
              <Button
                className="w-full"
                disabled={create.isPending || !title.trim() || !description.trim()}
                onClick={() =>
                  create.mutate({
                    title: title.trim(),
                    description: description.trim(),
                    location: location.trim() || undefined,
                    experience_min: experienceMin ? Number(experienceMin) : undefined,
                    required_skills: skills
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
              >
                {create.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Plus className="size-4" />
                )}
                Create job
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

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
                    <Badge variant={job.status === "open" ? "default" : "secondary"}>
                      {job.status}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {job.location ?? "Remote / unspecified"}
                    {job.experience_min ? ` · ${job.experience_min}+ yrs` : ""}
                  </p>
                  <p className="text-sm font-medium">
                    {job.application_count ?? 0} application{job.application_count === 1 ? "" : "s"}
                  </p>
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
