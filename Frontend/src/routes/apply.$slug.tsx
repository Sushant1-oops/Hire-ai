import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { motion } from "motion/react";
import { CheckCircle2, Loader2, Sparkles, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { publicJobQuery, submitApplication } from "@/lib/queries";

export const Route = createFileRoute("/apply/$slug")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Apply — HireAI" },
      { name: "description", content: "Submit your application." },
    ],
  }),
  component: ApplyPage,
});

function ApplyPage() {
  const { slug } = Route.useParams();
  const { data: job, isLoading, error } = useQuery(publicJobQuery(slug));

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const apply = useMutation({
    mutationFn: () =>
      submitApplication(slug, {
        full_name: fullName,
        email,
        phone: phone || undefined,
        resume: file!,
      }),
  });

  const pickFile = (files: FileList | null) => {
    const pdf = Array.from(files ?? []).find((f) => f.type === "application/pdf");
    if (!pdf) return;
    setFile(pdf);
  };

  const canSubmit = fullName.trim() && email.trim() && file && !apply.isPending;

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col items-center px-4 py-12">
      <div className="mb-8 flex items-center gap-2">
        <span className="flex size-9 items-center justify-center rounded-xl bg-primary">
          <Sparkles className="size-5 text-primary-foreground" />
        </span>
        <p className="text-lg font-semibold tracking-tight">HireAI</p>
      </div>

      {isLoading && (
        <div className="w-full space-y-3">
          <Skeleton className="h-8 w-2/3" />
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-40 w-full" />
        </div>
      )}

      {error && (
        <div className="w-full rounded-2xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-sm text-destructive">{(error as Error).message}</p>
        </div>
      )}

      {job && !apply.isSuccess && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full space-y-8"
        >
          <div className="text-center">
            <h1 className="text-2xl font-semibold tracking-tight">{job.title}</h1>
            <p className="mt-1 text-muted-foreground">
              {job.location ?? "Remote"}
              {job.experience_min ? ` · ${job.experience_min}+ years` : ""}
            </p>
            {!!job.required_skills?.length && (
              <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                {job.required_skills.map((s) => (
                  <Badge key={s} variant="secondary">
                    {s}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <article className="whitespace-pre-wrap rounded-2xl border border-border bg-card p-6 text-sm leading-relaxed shadow-soft">
            {job.description}
          </article>

          <div className="space-y-4 rounded-2xl border border-border bg-card p-6 shadow-soft">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="apply-name">Full name *</Label>
                <Input
                  id="apply-name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="apply-email">Email *</Label>
                <Input
                  id="apply-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="apply-phone">Phone</Label>
              <Input id="apply-phone" value={phone} onChange={(e) => setPhone(e.target.value)} />
            </div>

            <div className="space-y-2">
              <Label>Resume (PDF) *</Label>
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  pickFile(e.dataTransfer.files);
                }}
                onClick={() => inputRef.current?.click()}
                className={cn(
                  "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-border p-8 text-center transition-colors",
                  dragging && "border-primary bg-accent/50",
                )}
              >
                <input
                  ref={inputRef}
                  type="file"
                  accept="application/pdf"
                  hidden
                  onChange={(e) => pickFile(e.target.files)}
                />
                <UploadCloud className="size-6 text-muted-foreground" />
                <p className="mt-2 text-sm">
                  {file ? file.name : "Drop your resume here or click to browse"}
                </p>
              </div>
            </div>

            {apply.isError && (
              <p className="text-sm text-destructive">{(apply.error as Error).message}</p>
            )}

            <Button className="w-full" disabled={!canSubmit} onClick={() => apply.mutate()}>
              {apply.isPending ? <Loader2 className="size-4 animate-spin" /> : null}
              Apply now
            </Button>
          </div>
        </motion.div>
      )}

      {apply.isSuccess && (
        <motion.div
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex flex-col items-center gap-3 rounded-2xl border border-border bg-card p-10 text-center shadow-soft"
        >
          <CheckCircle2 className="size-10 text-success" />
          <p className="text-lg font-medium">Application received</p>
          <p className="text-sm text-muted-foreground">
            Thanks for applying to {apply.data?.job_title}. The team will be in touch if there's a
            match.
          </p>
        </motion.div>
      )}
    </div>
  );
}
