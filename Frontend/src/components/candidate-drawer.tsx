import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Mail, Phone, GraduationCap, Sparkles, Trash2, Loader2 } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import { deleteResume, resumeQuery } from "@/lib/queries";
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
    </Sheet>
  );
}
