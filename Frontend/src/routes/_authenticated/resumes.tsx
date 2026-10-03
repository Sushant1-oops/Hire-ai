import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { UploadCloud, Loader2, Trash2, RefreshCw, RotateCw, Search as SearchIcon } from "lucide-react";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
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
import { cn } from "@/lib/utils";
import { deleteResume, reindexResumes, reprocessResume, resumesQuery, uploadResumes } from "@/lib/queries";
import { CandidateDrawer, candidateName, candidateYears } from "@/components/candidate-drawer";
import { AiHub, type AiHubTarget } from "@/components/ai-hub";
import type { Resume } from "@/lib/types";

export const Route = createFileRoute("/_authenticated/resumes")({
  head: () => ({
    meta: [
      { title: "Resumes — HireAI Candidate Library" },
      {
        name: "description",
        content: "Upload resumes in bulk and browse parsed candidate profiles.",
      },
      { property: "og:title", content: "HireAI Resume Library" },
      {
        property: "og:description",
        content: "Drag and drop resumes and explore parsed candidate profiles.",
      },
    ],
  }),
  component: ResumesPage,
});

type Filter = "all" | "pending" | "failed" | "review";

function ResumesPage() {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    ...resumesQuery(),
    // Uploads are parsed in the background: keep refreshing while any are pending so
    // names, skills and status appear without a manual reload.
    refetchInterval: (query) =>
      (query.state.data ?? []).some((r) => r.processing_status === "pending") ? 4000 : false,
  });
  const all = data ?? [];
  const [filter, setFilter] = useState<Filter>("all");
  const [term, setTerm] = useState("");

  const counts = useMemo(
    () => ({
      all: all.length,
      pending: all.filter((r) => r.processing_status === "pending").length,
      failed: all.filter((r) => r.processing_status === "failed").length,
      review: all.filter((r) => r.needs_review).length,
    }),
    [all],
  );
  const resumes = useMemo(() => {
    const needle = term.trim().toLowerCase();
    return all.filter((r) => {
      if (filter === "pending" && r.processing_status !== "pending") return false;
      if (filter === "failed" && r.processing_status !== "failed") return false;
      if (filter === "review" && !r.needs_review) return false;
      if (!needle) return true;
      const haystack = [r.candidate_name, r.candidate_email, ...(r.skills ?? [])].join(" ").toLowerCase();
      return haystack.includes(needle);
    });
  }, [all, filter, term]);
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<string | number | null>(null);
  const [aiTarget, setAiTarget] = useState<AiHubTarget | null>(null);
  const [pendingDelete, setPendingDelete] = useState<{ id: number; name: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const upload = useMutation({
    mutationFn: uploadResumes,
    onSuccess: (result) => {
      const dupes = result.successful.filter((r) => r.duplicate).length;
      const added = result.successful.length - dupes;
      if (result.failed.length) toast.error(`${result.failed.length} file(s) rejected: ${result.failed[0]?.error}`);
      if (added) toast.success(`${added} resume(s) uploaded, parsing in the background`);
      if (dupes) toast.info(`${dupes} already in your library`);
      queryClient.invalidateQueries({ queryKey: ["resumes"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reindex = useMutation({
    mutationFn: reindexResumes,
    onSuccess: () => toast.success("Search index rebuilt — try your searches again"),
    onError: (e: Error) => toast.error(e.message),
  });

  const retry = useMutation({
    mutationFn: (id: number) => reprocessResume(id),
    onSuccess: () => {
      toast.success("Processing again…");
      queryClient.invalidateQueries({ queryKey: ["resumes"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const remove = useMutation({
    mutationFn: (id: number) => deleteResume(id),
    onMutate: async (id: number) => {
      setPendingDelete(null); // close the confirmation immediately — no need to wait on the network
      await queryClient.cancelQueries({ queryKey: ["resumes"] });
      const previous = queryClient.getQueryData<Resume[]>(["resumes"]);
      if (previous) {
        queryClient.setQueryData(
          ["resumes"],
          previous.filter((r) => r.id !== id),
        );
      }
      return { previous };
    },
    onSuccess: () => {
      toast.success("Resume deleted");
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e: Error, _id, context) => {
      if (context?.previous) queryClient.setQueryData(["resumes"], context.previous);
      toast.error(e.message);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["resumes"] }),
  });

  const handleFiles = (files: FileList | null) => {
    const pdfs = Array.from(files ?? []).filter((f) => f.type === "application/pdf");
    if (!pdfs.length) {
      toast.error("Please drop PDF files");
      return;
    }
    upload.mutate(pdfs);
  };

  return (
    <AppShell title="Resumes" description="Upload, parse and browse your candidate library">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-border bg-card p-8 text-center transition-colors",
          dragging && "border-primary bg-accent/50",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          multiple
          hidden
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = ""; // allow choosing the same file again
          }}
        />
        <motion.span
          animate={{ y: dragging ? -6 : 0 }}
          className="flex size-12 items-center justify-center rounded-2xl bg-accent text-accent-foreground"
        >
          {upload.isPending ? <Loader2 className="size-6 animate-spin" /> : <UploadCloud className="size-6" />}
        </motion.span>
        <p className="mt-4 font-medium">{upload.isPending ? "Uploading resumes..." : "Drop PDF resumes here"}</p>
        <p className="text-sm text-muted-foreground">or click to browse — up to 25 PDFs at a time</p>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-2">
        <div className="relative min-w-52 flex-1 sm:max-w-xs">
          <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={term}
            onChange={(e) => setTerm(e.target.value)}
            placeholder="Filter by name, email or skill"
            className="pl-9"
          />
        </div>
        {(
          [
            ["all", "All"],
            ["pending", "Processing"],
            ["review", "Needs check"],
            ["failed", "Failed"],
          ] as const
        ).map(([key, label]) =>
          key === "all" || counts[key] > 0 || filter === key ? (
            <Button
              key={key}
              size="sm"
              variant={filter === key ? "default" : "outline"}
              onClick={() => setFilter(key)}
            >
              {label} <span className="ml-1 opacity-70">{counts[key]}</span>
            </Button>
          ) : null,
        )}
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto"
          onClick={() => reindex.mutate()}
          disabled={reindex.isPending}
          title="Re-embeds your existing resumes with the current search strategy — only needed after an update, not for new uploads"
        >
          {reindex.isPending ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
          Rebuild search index
        </Button>
      </div>

      {error && (
        <p className="mt-6 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {(error as Error).message}
        </p>
      )}

      {isLoading && (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full rounded-2xl" />
          ))}
        </div>
      )}

      {!isLoading && !!resumes.length && (
        <div className="mt-8 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <AnimatePresence>
            {resumes.map((resume, i) => (
              <motion.div
                key={resume.id}
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ delay: Math.min(i * 0.04, 0.4) }}
                whileHover={{ y: -4 }}
              >
                <Card
                  onClick={() => setSelected(resume.id)}
                  className="group relative cursor-pointer shadow-soft transition-shadow hover:shadow-lg"
                >
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute right-2 top-2 size-7 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      setPendingDelete({ id: resume.id, name: candidateName(resume) });
                    }}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                  <CardContent className="pt-6">
                    <p className="truncate pr-6 font-medium">{candidateName(resume)}</p>
                    {resume.processing_status === "pending" && (
                      <Badge variant="outline" className="mt-1 gap-1">
                        <Loader2 className="size-3 animate-spin" /> Processing
                      </Badge>
                    )}
                    {resume.processing_status === "failed" && (
                      <div className="mt-1 flex items-center gap-2">
                        <Badge variant="destructive" title={resume.processing_error ?? undefined}>
                          Could not process
                        </Badge>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-6 px-2 text-xs"
                          disabled={retry.isPending}
                          onClick={(e) => {
                            e.stopPropagation();
                            retry.mutate(resume.id);
                          }}
                        >
                          <RotateCw className="size-3" /> Retry
                        </Button>
                      </div>
                    )}
                    {resume.processing_status !== "pending" && resume.needs_review && (
                      <Badge variant="outline" className="mt-1" title="Name or email could not be read confidently">
                        Check details
                      </Badge>
                    )}
                    <p className="text-sm text-muted-foreground">
                      {candidateYears(resume)} yrs experience
                    </p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {(resume.skills ?? []).slice(0, 4).map((s) => (
                        <Badge key={s} variant="secondary">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}

      {!isLoading && !resumes.length && !error && (
        <p className="mt-8 text-sm text-muted-foreground">
          {all.length ? "No resumes match this filter." : "No resumes yet — upload a few PDFs to get started."}
        </p>
      )}

      <CandidateDrawer
        resumeId={selected}
        onOpenChange={(open) => !open && setSelected(null)}
        onOpenAiHub={(target) =>
          setAiTarget({
            resumeId: target.id,
            name: target.candidate_name,
            email: target.candidate_email,
          })
        }
      />
      <AiHub target={aiTarget} onOpenChange={(open) => !open && setAiTarget(null)} />

      <AlertDialog open={!!pendingDelete} onOpenChange={(open) => !open && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this resume?</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDelete?.name ?? "This candidate"}'s resume and any associated search history,
              AI analysis, and job applications will be permanently deleted. This can't be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={remove.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={remove.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={(e) => {
                e.preventDefault();
                if (pendingDelete) remove.mutate(pendingDelete.id);
              }}
            >
              {remove.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AppShell>
  );
}
