import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Save, ScanSearch, Sparkles } from "lucide-react";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { mergeSkills, SkillInput, splitSkillText } from "@/components/skill-input";
import { useAuth } from "@/lib/auth";
import {
  createJob,
  extractSkills,
  generateJobDescription,
  updateJob,
  type JobInput,
} from "@/lib/queries";
import type { Job } from "@/lib/types";

/**
 * Create a job, or edit one when `job` is given. Editing the description, skills or
 * minimum experience re-scores the job's applicants on the server.
 */
export function JobFormDialog({
  open,
  onOpenChange,
  job,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  job?: Job | undefined;
  onSaved?: ((job: Job) => void) | undefined;
}) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const editing = !!job;

  const [title, setTitle] = useState("");
  const [location, setLocation] = useState("");
  const [experienceMin, setExperienceMin] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [skillDraft, setSkillDraft] = useState("");
  const [niceToHave, setNiceToHave] = useState<string[]>([]);
  const [roleSummary, setRoleSummary] = useState("");

  // Reset the form each time the dialog opens, from the job being edited (if any).
  useEffect(() => {
    if (!open) return;
    setTitle(job?.title ?? "");
    setLocation(job?.location ?? "");
    setExperienceMin(job?.experience_min != null ? String(job.experience_min) : "");
    setDescription(job?.description ?? "");
    setSkills(job?.required_skills ?? []);
    setSkillDraft("");
    setNiceToHave([]);
    setRoleSummary("");
  }, [open, job]);

  const save = useMutation({
    mutationFn: () => {
      const payload: JobInput = {
        title: title.trim(),
        description: description.trim(),
        location: location.trim() || null,
        experience_min: experienceMin.trim() ? Math.max(0, Number(experienceMin)) : null,
        // Anything still typed in the skills box counts.
        required_skills: mergeSkills(skills, splitSkillText(skillDraft)),
      };
      return job ? updateJob(job.id, payload) : createJob(payload);
    },
    onSuccess: (saved) => {
      toast.success(editing ? "Job updated" : "Job created — share the apply link with candidates");
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      onSaved?.(saved);
      onOpenChange(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const draft = useMutation({
    mutationFn: () =>
      generateJobDescription({
        job_title: title.trim(),
        job_shorthand: roleSummary.trim(),
        company_name: user?.company ?? undefined,
      }),
    onSuccess: (data) => {
      setDescription(data.job_description);
      setSkills(data.required_skills);
      setSkillDraft("");
      setNiceToHave(data.nice_to_have_skills);
      if (data.experience_min != null && !experienceMin.trim()) {
        setExperienceMin(String(data.experience_min));
      }
      toast.success("Draft ready — review and edit before saving");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const detect = useMutation({
    mutationFn: () => extractSkills(description),
    onSuccess: (data) => {
      if (!data.skills.length) {
        toast.info("No known skills found in the description — add them manually");
        return;
      }
      setSkills((current) => mergeSkills(current, data.skills));
      toast.success(`Found ${data.skills.length} skill(s) in the description`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const canSave = title.trim().length >= 2 && description.trim().length >= 10 && !save.isPending;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit job" : "Create a job posting"}</DialogTitle>
          <DialogDescription>
            {editing
              ? "Changing the description, skills or experience re-scores every applicant."
              : "HireAI generates a public apply link — candidates don't need an account."}
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
              max={50}
              step={0.5}
              value={experienceMin}
              onChange={(e) => setExperienceMin(e.target.value)}
            />
          </div>

          {!editing && (
            <div className="space-y-2 rounded-xl border border-dashed border-border p-3">
              <Label htmlFor="job-role-summary">Draft with AI (optional)</Label>
              <Textarea
                id="job-role-summary"
                value={roleSummary}
                onChange={(e) => setRoleSummary(e.target.value)}
                placeholder="Senior backend engineer for a fintech platform, Python + Django, 5+ years"
                className="min-h-20"
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={draft.isPending || !title.trim() || !roleSummary.trim()}
                onClick={() => draft.mutate()}
              >
                {draft.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Sparkles className="size-4" />
                )}
                Generate description &amp; skills
              </Button>
              {!title.trim() && (
                <p className="text-xs text-muted-foreground">Add a job title above first.</p>
              )}
              {niceToHave.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-xs text-muted-foreground">
                    Nice to have (click to add as required):
                  </span>
                  {niceToHave.map((skill) => (
                    <button
                      key={skill}
                      type="button"
                      onClick={() => setSkills((cur) => mergeSkills(cur, [skill]))}
                    >
                      <Badge variant="outline" className="text-xs hover:bg-accent">
                        {skill}
                      </Badge>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="job-description">Job description</Label>
            <Textarea
              id="job-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="min-h-40"
            />
          </div>

          <div className="space-y-2">
            <SkillInput
              label="Required skills"
              skills={skills}
              onChange={setSkills}
              draft={skillDraft}
              onDraftChange={setSkillDraft}
              placeholder="Python, FastAPI, PostgreSQL"
              hint="Candidates are scored on these. Leave empty to detect them from the description."
            />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={detect.isPending || description.trim().length < 10}
              onClick={() => detect.mutate()}
            >
              {detect.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <ScanSearch className="size-4" />
              )}
              Detect skills from description
            </Button>
          </div>

          <Button className="w-full" disabled={!canSave} onClick={() => save.mutate()}>
            {save.isPending ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
            {editing ? "Save changes" : "Create job"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
