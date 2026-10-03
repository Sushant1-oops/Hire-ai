import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";
import { Search as SearchIcon, Loader2, Sparkles, Plus } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { ScoreRing, MetricBar } from "@/components/score-ring";
import { CandidateDrawer } from "@/components/candidate-drawer";
import { AiHub, type AiHubTarget } from "@/components/ai-hub";
import { AddToJobDialog } from "@/components/add-to-job-dialog";
import { RecommendationBadge } from "@/components/recommendation-badge";
import { mergeSkills, SkillInput, splitSkillText } from "@/components/skill-input";
import { jobsQuery, runSearch } from "@/lib/queries";
import type { SearchResult } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/search")({
  head: () => ({
    meta: [
      { title: "Semantic Search — HireAI Candidate Matching" },
      {
        name: "description",
        content:
          "Search your resume library with natural language, skill filters and experience thresholds to rank candidates.",
      },
      { property: "og:title", content: "HireAI Semantic Candidate Search" },
      {
        property: "og:description",
        content: "Rank candidates by semantic fit, skill overlap and experience match.",
      },
    ],
  }),
  component: SearchPage,
});

function SearchPage() {
  const [query, setQuery] = useState("");
  const [required, setRequired] = useState<string[]>([]);
  const [requiredDraft, setRequiredDraft] = useState("");
  const [nice, setNice] = useState<string[]>([]);
  const [niceDraft, setNiceDraft] = useState("");
  const [minExperience, setMinExperience] = useState(0);
  const [jobDescription, setJobDescription] = useState("");
  const [selected, setSelected] = useState<string | number | null>(null);
  const [aiTarget, setAiTarget] = useState<AiHubTarget | null>(null);
  const [strict, setStrict] = useState(false);
  const [addToJob, setAddToJob] = useState<{ id: number; name?: string | null | undefined } | null>(null);
  const { data: jobs } = useQuery(jobsQuery());

  // Start from an existing job: its title, description, skills and minimum experience prefill the form.
  const loadJob = (id: string) => {
    const job = jobs?.find((j) => String(j.id) === id);
    if (!job) return;
    setQuery(job.title);
    setJobDescription(job.description);
    setRequired(job.required_skills ?? []);
    setRequiredDraft("");
    setMinExperience(Math.min(20, Math.round(job.experience_min ?? 0)));
  };

  const search = useMutation({
    mutationFn: () => {
      // Commit anything still sitting in either skill box before searching —
      // typing a skill and hitting "Search" should always use it, the same as
      // pressing Enter first would have.
      const effectiveRequired = mergeSkills(required, splitSkillText(requiredDraft));
      const effectiveNice = mergeSkills(nice, splitSkillText(niceDraft));
      if (requiredDraft.trim()) {
        setRequired(effectiveRequired);
        setRequiredDraft("");
      }
      if (niceDraft.trim()) {
        setNice(effectiveNice);
        setNiceDraft("");
      }
      return runSearch({
        query,
        required_skills: effectiveRequired,
        nice_to_have_skills: effectiveNice,
        min_experience: minExperience,
        job_description: jobDescription || undefined,
        // Strict mode turns the soft preferences into hard filters.
        must_have_skills: strict && effectiveRequired.length ? effectiveRequired : undefined,
        hard_min_experience: strict && minExperience > 0 ? minExperience : undefined,
      });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const results: SearchResult[] = search.data?.results ?? [];

  return (
    <AppShell
      title="Semantic Search"
      description="Describe the role in plain language and rank your candidate pool"
    >
      <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
        <Card className="h-fit shadow-soft lg:sticky lg:top-24">
          <CardContent className="space-y-5 pt-6">
            {!!jobs?.length && (
              <div className="space-y-2">
                <Label>Start from a job (optional)</Label>
                <Select onValueChange={loadJob}>
                  <SelectTrigger>
                    <SelectValue placeholder="Pick one of your jobs" />
                  </SelectTrigger>
                  <SelectContent>
                    {jobs.map((job) => (
                      <SelectItem key={job.id} value={String(job.id)}>
                        {job.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label>What are you hiring for?</Label>
              <Textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Senior backend engineer with Python and distributed systems experience"
                className="min-h-24"
              />
            </div>

            <SkillInput
              label="Required skills"
              skills={required}
              onChange={setRequired}
              draft={requiredDraft}
              onDraftChange={setRequiredDraft}
              placeholder="Python"
            />
            <SkillInput
              label="Nice to have"
              skills={nice}
              onChange={setNice}
              draft={niceDraft}
              onDraftChange={setNiceDraft}
              placeholder="Kubernetes"
            />

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Minimum experience</Label>
                <span className="text-sm font-medium">{minExperience} yrs</span>
              </div>
              <Slider
                value={[minExperience]}
                onValueChange={([v]) => setMinExperience(v ?? 0)}
                min={0}
                max={20}
                step={1}
              />
            </div>

            <div className="space-y-2">
              <Label>Job description (optional)</Label>
              <Textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Paste the full JD for a more precise semantic match"
                className="min-h-24"
              />
            </div>

            <div className="flex items-start justify-between gap-3 rounded-lg border border-border p-3">
              <div>
                <Label htmlFor="strict-mode">Strict matching</Label>
                <p className="text-xs text-muted-foreground">
                  Only show candidates that have every required skill and meet the minimum experience.
                </p>
              </div>
              <Switch id="strict-mode" checked={strict} onCheckedChange={setStrict} />
            </div>

            <Button
              className="w-full"
              onClick={() => search.mutate()}
              disabled={search.isPending || !query.trim()}
            >
              {search.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <SearchIcon className="size-4" />
              )}
              Search candidates
            </Button>
          </CardContent>
        </Card>

        <div className="space-y-4">
          {search.isPending && (
            <div className="space-y-4">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-40 w-full rounded-xl" />
              ))}
            </div>
          )}

          {search.isError && (
            <p className="text-sm text-destructive">{(search.error as Error).message}</p>
          )}

          {search.isSuccess && !results.length && (
            <Card className="shadow-soft">
              <CardContent className="py-16 text-center text-sm text-muted-foreground">
                No candidates matched. Try turning off strict matching or loosening the required skills.
              </CardContent>
            </Card>
          )}

          <AnimatePresence mode="popLayout">
            {results.map((result, index) => {
              const id = result.resume_id;
              return (
                <motion.div
                  key={String(id)}
                  layout
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ delay: index * 0.05, duration: 0.3 }}
                >
                  <Card className="shadow-soft transition-shadow hover:shadow-lg">
                    <CardContent className="space-y-4 pt-6">
                      <div className="flex items-start gap-4">
                        <ScoreRing value={result.final_score} label="fit" />
                        <div className="min-w-0 flex-1">
                          <button
                            className="truncate text-left text-base font-semibold hover:underline"
                            onClick={() => setSelected(id)}
                          >
                            {result.candidate_name ?? `Candidate ${id}`}
                          </button>
                          <p className="truncate text-sm text-muted-foreground">
                            {result.candidate_email ?? "No email on file"} ·{" "}
                            {result.experience_years ?? 0} yrs
                          </p>
                          <RecommendationBadge value={result.recommendation} className="mt-2" />
                        </div>
                        <div className="flex shrink-0 flex-col gap-2">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() =>
                              setAiTarget({
                                resumeId: id,
                                name: result.candidate_name,
                                email: result.candidate_email,
                                query,
                              })
                            }
                          >
                            <Sparkles className="size-4" /> AI Hub
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setAddToJob({ id, name: result.candidate_name })}
                          >
                            <Plus className="size-4" /> Add to job
                          </Button>
                        </div>
                      </div>

                      {result.evidence_snippet && (
                        <p className="line-clamp-2 rounded-lg bg-muted px-3 py-2 text-xs italic text-muted-foreground">
                          “{result.evidence_snippet}”
                        </p>
                      )}

                      <div className="grid gap-3 sm:grid-cols-3">
                        <MetricBar label="Semantic" value={result.semantic_similarity} />
                        <MetricBar label="Skills" value={result.skill_overlap} />
                        <MetricBar label="Experience" value={result.experience_match} />
                      </div>

                      <div className="flex flex-wrap gap-1.5">
                        {(result.matched_skills ?? []).map((s) => (
                          <Badge key={`m-${s}`} variant="outline" className="border-success/40 bg-success/10 text-success">
                            ✓ {s}
                          </Badge>
                        ))}
                        {(result.missing_skills ?? []).map((s) => (
                          <Badge key={`x-${s}`} variant="outline" className="border-destructive/30 text-destructive">
                            ✗ {s}
                          </Badge>
                        ))}
                      </div>
                    </CardContent>
                  </Card>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>

      <CandidateDrawer
        resumeId={selected}
        onOpenChange={(open) => !open && setSelected(null)}
        onOpenAiHub={(target) =>
          setAiTarget({
            resumeId: target.id,
            name: target.candidate_name,
            email: target.candidate_email,
            query,
          })
        }
      />
      <AiHub target={aiTarget} onOpenChange={(open) => !open && setAiTarget(null)} />
      <AddToJobDialog
        resumeId={addToJob?.id ?? null}
        candidateName={addToJob?.name}
        onOpenChange={(open) => !open && setAddToJob(null)}
      />
    </AppShell>
  );
}
