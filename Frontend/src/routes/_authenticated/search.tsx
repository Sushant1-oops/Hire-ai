import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";
import { Search as SearchIcon, Loader2, Sparkles, X, Plus } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { ScoreRing, MetricBar } from "@/components/score-ring";
import { CandidateDrawer } from "@/components/candidate-drawer";
import { AiHub, type AiHubTarget } from "@/components/ai-hub";
import { runSearch } from "@/lib/queries";
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

function SkillInput({
  label,
  skills,
  onChange,
  placeholder,
}: {
  label: string;
  skills: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const value = draft.trim();
    if (!value || skills.includes(value)) return setDraft("");
    onChange([...skills, value]);
    setDraft("");
  };
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
        />
        <Button
          type="button"
          variant="secondary"
          size="icon"
          onClick={add}
          aria-label={`Add ${label}`}
        >
          <Plus className="size-4" />
        </Button>
      </div>
      {!!skills.length && (
        <div className="flex flex-wrap gap-1.5">
          {skills.map((skill) => (
            <Badge key={skill} variant="secondary" className="gap-1">
              {skill}
              <button
                type="button"
                onClick={() => onChange(skills.filter((s) => s !== skill))}
                aria-label={`Remove ${skill}`}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function SearchPage() {
  const [query, setQuery] = useState("");
  const [required, setRequired] = useState<string[]>([]);
  const [nice, setNice] = useState<string[]>([]);
  const [minExperience, setMinExperience] = useState(0);
  const [jobDescription, setJobDescription] = useState("");
  const [selected, setSelected] = useState<string | number | null>(null);
  const [aiTarget, setAiTarget] = useState<AiHubTarget | null>(null);

  const search = useMutation({
    mutationFn: () =>
      runSearch({
        query,
        required_skills: required,
        nice_to_have_skills: nice,
        min_experience: minExperience,
        job_description: jobDescription || undefined,
      }),
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
              placeholder="Python"
            />
            <SkillInput
              label="Nice to have"
              skills={nice}
              onChange={setNice}
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
                No candidates matched. Try loosening the required skills or experience.
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
                          {result.recommendation && (
                            <p className="mt-2 text-sm leading-relaxed">{result.recommendation}</p>
                          )}
                        </div>
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
                      </div>

                      <div className="grid gap-3 sm:grid-cols-3">
                        <MetricBar label="Semantic" value={result.semantic_similarity} />
                        <MetricBar label="Skills" value={result.skill_overlap} />
                        <MetricBar label="Experience" value={result.experience_match} />
                      </div>

                      <div className="flex flex-wrap gap-1.5">
                        {(result.matched_skills ?? []).map((s) => (
                          <Badge key={`m-${s}`} variant="secondary">
                            {s}
                          </Badge>
                        ))}
                        {(result.missing_skills ?? []).map((s) => (
                          <Badge key={`x-${s}`} variant="outline" className="text-muted-foreground">
                            {s}
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
    </AppShell>
  );
}
