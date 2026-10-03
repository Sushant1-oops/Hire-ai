import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Mail, Phone, GraduationCap, Sparkles, Trash2, Loader2, FileText, Pencil, Briefcase, Plus } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { AddToJobDialog } from "@/components/add-to-job-dialog";
import { deleteResume, openResumeFile, resumeQuery, updateResume } from "@/lib/queries";
import type { Resume } from "@/lib/types";
import { toast } from "sonner";

export function candidateName(resume: { candidate_name?: string | null } | undefined) {
  return resume?.candidate_name?.trim() || "Unnamed candidate";
}

export function candidateYears(resume: { experience_years?: number | null } | undefined) {
  return resume?.experience_years ?? 0;
}

export interface CandidateTarget {
  id: number;
  candidate_name?: string | null | undefined;
  candidate_email?: string | null | undefined;
}

export function CandidateDrawer({
  resumeId,
  onOpenChange,
  onOpenAiHub,
}: {
  resumeId: string | number | null;
  onOpenChange: (open: boolean) => void;
  onOpenAiHub: (resume: CandidateTarget) => void;
}) {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    ...resumeQuery(resumeId ?? ""),
    enabled: resumeId !== null,
  });
  const [addToJobFor, setAddToJobFor] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", phone: "", years: "" });

  // Leaving edit mode whenever a different candidate is opened.
  useEffect(() => setEditing(false), [resumeId]);

  const save = useMutation({
    mutationFn: () =>
      updateResume(data!.id, {
        candidate_name: form.name.trim() || null,
        candidate_email: form.email.trim() || null,
        candidate_phone: form.phone.trim() || null,
        experience_years: form.years.trim() ? Number(form.years) : null,
      }),
    onSuccess: () => {
      toast.success("Details saved");
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["resumes"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] }); // experience feeds the job scores
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const startEdit = () => {
    if (!data) return;
    setForm({
      name: data.candidate_name ?? "",
      email: data.candidate_email ?? "",
      phone: data.candidate_phone ?? "",
      years: data.experience_years != null ? String(data.experience_years) : "",
    });
    setEditing(true);
  };

  const remove = useMutation({
    mutationFn: (id: number) => deleteResume(id),
    onMutate: (id: number) => {
      onOpenChange(false); // close immediately — no need to wait on the network
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
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (e: Error, _id, context) => {
      if (context?.previous) queryClient.setQueryData(["resumes"], context.previous);
      toast.error(e.message);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["resumes"] }),
  });

  return (
    <Sheet open={resumeId !== null} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{isLoading ? "Loading candidate" : candidateName(data)}</SheetTitle>
          <SheetDescription>
            {data ? `${candidateYears(data)} yrs experience` : "Parsed resume details"}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-6 px-4 pb-8">
          {isLoading && (
            <div className="space-y-3">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
          )}
          {error && <p className="text-sm text-destructive">{(error as Error).message}</p>}

          {data && (
            <>
              {data.needs_review && (
                <p className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-muted-foreground">
                  The name or email in this resume couldn't be read with confidence
                  {data.used_ocr ? " (scanned PDF, text came from OCR)" : ""}. Please check the details below.
                </p>
              )}
              {editing ? (
                <div className="space-y-3 rounded-xl border border-border p-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="cd-name">Name</Label>
                    <Input id="cd-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="cd-email">Email</Label>
                      <Input id="cd-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="cd-phone">Phone</Label>
                      <Input id="cd-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="cd-years">Years of experience</Label>
                    <Input id="cd-years" type="number" min={0} max={60} step={0.5} value={form.years} onChange={(e) => setForm({ ...form, years: e.target.value })} />
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" disabled={save.isPending} onClick={() => save.mutate()}>
                      {save.isPending ? <Loader2 className="size-4 animate-spin" /> : null} Save
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-2 text-sm">
                  {data.candidate_email && (
                    <p className="flex items-center gap-2">
                      <Mail className="size-4 text-muted-foreground" /> {data.candidate_email}
                    </p>
                  )}
                  {data.candidate_phone && (
                    <p className="flex items-center gap-2">
                      <Phone className="size-4 text-muted-foreground" /> {data.candidate_phone}
                    </p>
                  )}
                  <Button variant="ghost" size="sm" className="-ml-2" onClick={startEdit}>
                    <Pencil className="size-3.5" /> Edit details
                  </Button>
                </div>
              )}

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <p className="flex items-center gap-2 text-sm font-semibold">
                    <Briefcase className="size-4 text-muted-foreground" /> Jobs
                  </p>
                  <Button variant="ghost" size="sm" disabled={data.processing_status !== "ready"} onClick={() => setAddToJobFor(data.id)}>
                    <Plus className="size-3.5" /> Add to job
                  </Button>
                </div>
                {data.applications?.length ? (
                  <ul className="space-y-1.5 text-sm">
                    {data.applications.map((a) => (
                      <li key={a.application_id} className="flex items-center justify-between gap-2 rounded-lg bg-muted px-3 py-2">
                        <Link to="/jobs/$jobId" params={{ jobId: String(a.job_id) }} className="truncate font-medium hover:underline">
                          {a.job_title}
                        </Link>
                        <span className="shrink-0 text-xs capitalize text-muted-foreground">
                          {a.status}
                          {a.score != null ? ` · ${Math.round(a.score * 100)}%` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground">Not attached to any job yet.</p>
                )}
              </div>

              {!!data.skills?.length && (
                <div>
                  <p className="mb-2 text-sm font-semibold">Skills</p>
                  <div className="flex flex-wrap gap-1.5">
                    {data.skills.map((s) => (
                      <Badge key={s} variant="secondary">
                        {s}
                      </Badge>
                    ))}
                  </div>
                </div>
              )}

              {!!data.education?.length && (
                <div>
                  <p className="mb-2 flex items-center gap-2 text-sm font-semibold">
                    <GraduationCap className="size-4 text-muted-foreground" /> Education
                  </p>
                  <ul className="space-y-1 text-sm text-muted-foreground">
                    {data.education.map((e, i) => (
                      <li key={i}>{e.degree}</li>
                    ))}
                  </ul>
                </div>
              )}

              {data.extracted_text && (
                <div>
                  <p className="mb-2 text-sm font-semibold">Resume snippet</p>
                  <p className="max-h-56 overflow-y-auto rounded-xl bg-muted p-4 text-xs leading-relaxed whitespace-pre-wrap text-muted-foreground">
                    {data.extracted_text.slice(0, 1500)}
                  </p>
                </div>
              )}

              <div className="flex gap-2">
                <Button
                  className="flex-1"
                  onClick={() =>
                    onOpenAiHub({
                      id: data.id,
                      candidate_name: data.candidate_name,
                      candidate_email: data.candidate_email,
                    })
                  }
                >
                  <Sparkles className="size-4" /> Open AI Recruitment Hub
                </Button>

                <Button
                  variant="outline"
                  size="icon"
                  className="shrink-0"
                  title="Open original PDF"
                  onClick={() => openResumeFile(data.id).catch((e: Error) => toast.error(e.message))}
                >
                  <FileText className="size-4" />
                </Button>

                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" size="icon" className="shrink-0 text-destructive">
                      <Trash2 className="size-4" />
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete this resume?</AlertDialogTitle>
                      <AlertDialogDescription>
                        {candidateName(data)}'s resume and any associated search history, AI
                        analysis, and job applications will be permanently deleted. This can't be
                        undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel disabled={remove.isPending}>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        disabled={remove.isPending}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        onClick={(e) => {
                          e.preventDefault();
                          remove.mutate(data.id);
                        }}
                      >
                        {remove.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </>
          )}
        </div>
      </SheetContent>
      <AddToJobDialog
        resumeId={addToJobFor}
        candidateName={data?.candidate_name}
        onOpenChange={(open) => !open && setAddToJobFor(null)}
      />
    </Sheet>
  );
}
