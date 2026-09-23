import { useMutation } from "@tanstack/react-query";
import { motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";
import { Loader2, Sparkles, Mail, Send, FileText, Brain } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/lib/auth";
import {
  analyzeMatch,
  generateEmail,
  generateJobDescription,
  generateQuestions,
  sendEmail,
} from "@/lib/queries";

export interface AiHubTarget {
  resumeId: string | number;
  name?: string | null | undefined;
  email?: string | null | undefined;
  /** Free-text search query or job description already known about this candidate, used to prefill the JD field. */
  query?: string | undefined;
  tab?: "analysis" | "questions" | "email" | "jd" | undefined;
}

export function AiHub({
  target,
  onOpenChange,
}: {
  target: AiHubTarget | null;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Sheet open={!!target} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        {target && <AiHubBody target={target} />}
      </SheetContent>
    </Sheet>
  );
}

function AiHubBody({ target }: { target: AiHubTarget }) {
  const { user } = useAuth();
  // The backend requires a job title and/or job description for match analysis,
  // question generation and outreach emails — these are shared across all three tabs.
  const [jobTitle, setJobTitle] = useState("");
  const [jobDescription, setJobDescription] = useState(target.query ?? "");
  const [emailType, setEmailType] = useState("interview_invite");
  // Pre-filled from the logged-in HR user so the generated email never has to
  // fall back to a generic "Hiring Team"/"[Company Name]" placeholder — still
  // editable in case this email should come from someone else.
  const [companyName, setCompanyName] = useState(user?.company ?? "");
  const [contactPerson, setContactPerson] = useState(user?.full_name ?? "");
  const [interviewDate, setInterviewDate] = useState("");
  const [interviewTime, setInterviewTime] = useState("");
  const [interviewLocation, setInterviewLocation] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [jdSummary, setJdSummary] = useState("");

  const analysis = useMutation({
    mutationFn: () => analyzeMatch({ resume_id: target.resumeId, job_description: jobDescription }),
    onError: (e: Error) => toast.error(e.message),
  });
  const questions = useMutation({
    mutationFn: () =>
      generateQuestions({
        resume_id: target.resumeId,
        job_title: jobTitle,
        job_description: jobDescription || undefined,
      }),
    onError: (e: Error) => toast.error(e.message),
  });
  const email = useMutation({
    mutationFn: () =>
      generateEmail({
        resume_id: target.resumeId,
        email_type: emailType,
        job_title: jobTitle,
        company_name: companyName || undefined,
        contact_person: contactPerson || undefined,
        interview_date: emailType === "interview_invite" ? interviewDate || undefined : undefined,
        interview_time: emailType === "interview_invite" ? interviewTime || undefined : undefined,
        interview_location:
          emailType === "interview_invite" ? interviewLocation || undefined : undefined,
      }),
    onSuccess: (data) => {
      setSubject(data.subject_line ?? "");
      setBody(data.email_body ?? "");
      toast.success("Draft ready below — review it, then send");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const send = useMutation({
    mutationFn: () => sendEmail({ to_email: target.email ?? "", subject, body }),
    onSuccess: () => toast.success(`Email sent to ${target.email}`),
    onError: (e: Error) => toast.error(e.message),
  });
  const jd = useMutation({
    mutationFn: () =>
      generateJobDescription({ job_title: jobTitle || jdSummary, job_shorthand: jdSummary }),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <>
      <SheetHeader>
        <SheetTitle className="flex items-center gap-2">
          <Sparkles className="size-4 text-primary" /> AI Recruitment Hub
        </SheetTitle>
        <SheetDescription>{target.name ?? "Candidate"} — AI assisted hiring tools</SheetDescription>
      </SheetHeader>

      <div className="grid gap-4 px-4 pt-2 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="ai-hub-job-title">Job title</Label>
          <Input
            id="ai-hub-job-title"
            value={jobTitle}
            onChange={(e) => setJobTitle(e.target.value)}
            placeholder="Senior Backend Engineer"
          />
        </div>
      </div>
      <div className="space-y-2 px-4 pt-4">
        <Label htmlFor="ai-hub-job-description">Job description</Label>
        <Textarea
          id="ai-hub-job-description"
          value={jobDescription}
          onChange={(e) => setJobDescription(e.target.value)}
          placeholder="Paste the role's job description — used for match analysis and interview questions"
          className="min-h-20"
        />
      </div>

      <Tabs defaultValue={target.tab ?? "analysis"} className="px-4 pb-8 pt-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="analysis">Match</TabsTrigger>
          <TabsTrigger value="questions">Questions</TabsTrigger>
          <TabsTrigger value="email">Email</TabsTrigger>
          <TabsTrigger value="jd">JD</TabsTrigger>
        </TabsList>

        <TabsContent value="analysis" className="space-y-4 pt-4">
          <Button
            onClick={() => analysis.mutate()}
            disabled={analysis.isPending || !jobDescription.trim()}
          >
            {analysis.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Brain className="size-4" />
            )}
            Analyze match
          </Button>
          {!jobDescription.trim() && (
            <p className="text-xs text-muted-foreground">
              Add a job description above to run this.
            </p>
          )}
          {analysis.isPending && <ListSkeleton />}
          {analysis.data && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              <div className="flex items-center gap-2">
                <Badge>{analysis.data.recommendation}</Badge>
                <span className="text-sm text-muted-foreground">
                  {Math.round(analysis.data.match_score * 100)}% match
                </span>
              </div>
              {analysis.data.explanation && (
                <p className="rounded-xl bg-muted p-4 text-sm leading-relaxed">
                  {analysis.data.explanation}
                </p>
              )}
              {!!analysis.data.security_flags?.length && (
                <p className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-muted-foreground">
                  This resume contains text that reads like instructions to an AI. It was treated as
                  plain data and did not affect the score.
                </p>
              )}
              {!!analysis.data.evidence?.some((e) => !e.supported) && (
                <p className="text-xs text-muted-foreground">
                  {analysis.data.evidence.filter((e) => !e.supported).length} strength(s) below could not
                  be matched to text in the resume. Treat them with caution.
                </p>
              )}
              <BulletCard title="Strengths" tone="success" items={analysis.data.strengths} />
              <BulletCard title="Weaknesses" tone="destructive" items={analysis.data.weaknesses} />
              <SkillList
                title="Missing skills"
                skills={analysis.data.missing_skills}
                variant="secondary"
              />
            </motion.div>
          )}
        </TabsContent>

        <TabsContent value="questions" className="space-y-4 pt-4">
          <Button
            onClick={() => questions.mutate()}
            disabled={questions.isPending || !jobTitle.trim()}
          >
            {questions.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <FileText className="size-4" />
            )}
            Generate questions
          </Button>
          {!jobTitle.trim() && (
            <p className="text-xs text-muted-foreground">Add a job title above to run this.</p>
          )}
          {questions.isPending && <ListSkeleton />}
          {questions.data && (
            <Accordion type="single" collapsible defaultValue="technical_questions">
              {(
                [
                  { key: "technical_questions", label: "Technical" },
                  { key: "behavioral_questions", label: "Behavioral" },
                  { key: "practical_tasks", label: "Practical" },
                ] as const
              ).map(({ key, label }) => (
                <AccordionItem key={key} value={key}>
                  <AccordionTrigger>{label}</AccordionTrigger>
                  <AccordionContent>
                    <ol className="list-decimal space-y-2 pl-5 text-sm">
                      {(questions.data?.[key] ?? []).map((q, i) => (
                        <li key={i}>{q}</li>
                      ))}
                    </ol>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>
          )}
        </TabsContent>

        <TabsContent value="email" className="space-y-4 pt-4">
          <p className="text-xs text-muted-foreground">
            Generate drafts an editable email below — nothing is sent until you review it and press
            Send.
          </p>
          <div className="space-y-2">
            <Label>Email type</Label>
            <Select value={emailType} onValueChange={setEmailType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="interview_invite">Interview invite</SelectItem>
                <SelectItem value="rejection">Rejection</SelectItem>
                <SelectItem value="offer">Offer</SelectItem>
                <SelectItem value="follow_up">Follow up</SelectItem>
                <SelectItem value="cold_outreach">Cold outreach</SelectItem>
                <SelectItem value="thank_you">Thank you</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="ai-hub-company">Company</Label>
              <Input
                id="ai-hub-company"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Your company name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ai-hub-contact">Signed by</Label>
              <Input
                id="ai-hub-contact"
                value={contactPerson}
                onChange={(e) => setContactPerson(e.target.value)}
                placeholder="Your name"
              />
            </div>
          </div>
          {emailType === "interview_invite" && (
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="ai-hub-interview-date">Interview date</Label>
                <Input
                  id="ai-hub-interview-date"
                  value={interviewDate}
                  onChange={(e) => setInterviewDate(e.target.value)}
                  placeholder="e.g. Thu, Oct 2"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ai-hub-interview-time">Time</Label>
                <Input
                  id="ai-hub-interview-time"
                  value={interviewTime}
                  onChange={(e) => setInterviewTime(e.target.value)}
                  placeholder="e.g. 3:00 PM IST"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ai-hub-interview-location">Location / link</Label>
                <Input
                  id="ai-hub-interview-location"
                  value={interviewLocation}
                  onChange={(e) => setInterviewLocation(e.target.value)}
                  placeholder="Google Meet link or address"
                />
              </div>
            </div>
          )}
          <Button onClick={() => email.mutate()} disabled={email.isPending || !jobTitle.trim()}>
            {email.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Mail className="size-4" />
            )}
            Generate email
          </Button>
          {!jobTitle.trim() && (
            <p className="text-xs text-muted-foreground">Add a job title above to run this.</p>
          )}
          {email.isSuccess && !subject.trim() && !body.trim() && (
            <p className="text-sm text-destructive">
              The draft came back empty. This usually means the AI provider didn't return a
              well-formed response — try Generate again, or check the LLM provider config on the
              backend (a hosted provider like Groq is far more reliable at this than a small local
              Ollama model).
            </p>
          )}
          {(subject || body) && (
            <div className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-soft">
              <div className="space-y-2">
                <Label>Subject</Label>
                <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Message</Label>
                <Textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  className="min-h-56 whitespace-pre-wrap"
                />
              </div>
              <Button
                onClick={() => send.mutate()}
                disabled={send.isPending || !target.email}
                className="w-full"
              >
                {send.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Send className="size-4" />
                )}
                Send to {target.email ?? "candidate"}
              </Button>
              {!target.email && (
                <p className="text-xs text-muted-foreground">
                  No email on file for this candidate — can't send.
                </p>
              )}
            </div>
          )}
        </TabsContent>

        <TabsContent value="jd" className="space-y-4 pt-4">
          <div className="space-y-2">
            <Label>Role summary</Label>
            <Textarea
              value={jdSummary}
              onChange={(e) => setJdSummary(e.target.value)}
              placeholder="Senior backend engineer for a fintech platform, Python + Django, 5+ years"
              className="min-h-28"
            />
          </div>
          <Button
            onClick={() => jd.mutate()}
            disabled={jd.isPending || !jdSummary.trim() || !jobTitle.trim()}
          >
            {jd.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Sparkles className="size-4" />
            )}
            Generate job description
          </Button>
          {(!jobTitle.trim() || !jdSummary.trim()) && (
            <p className="text-xs text-muted-foreground">
              Add a job title above and a role summary to run this.
            </p>
          )}
          {jd.isPending && <ListSkeleton />}
          {jd.data && (
            <div className="space-y-4">
              <article className="whitespace-pre-wrap rounded-xl border border-border bg-card p-4 text-sm leading-relaxed shadow-soft">
                {jd.data.job_description}
              </article>
              <SkillList title="Required skills" skills={jd.data.required_skills} />
              <SkillList
                title="Nice to have"
                skills={jd.data.nice_to_have_skills}
                variant="secondary"
              />
            </div>
          )}
        </TabsContent>
      </Tabs>
    </>
  );
}

function BulletCard({
  title,
  items,
  tone,
}: {
  title: string;
  items?: string[] | undefined;
  tone: "success" | "destructive";
}) {
  if (!items?.length) return null;
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-soft">
      <p className="mb-2 text-sm font-semibold">{title}</p>
      <ul className="space-y-1.5 text-sm">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2">
            <span
              className={
                tone === "success"
                  ? "mt-1.5 size-1.5 shrink-0 rounded-full bg-success"
                  : "mt-1.5 size-1.5 shrink-0 rounded-full bg-destructive"
              }
            />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function SkillList({
  title,
  skills,
  variant = "default",
}: {
  title: string;
  skills?: string[] | undefined;
  variant?: "default" | "secondary" | undefined;
}) {
  if (!skills?.length) return null;
  return (
    <div>
      <p className="mb-2 text-sm font-semibold">{title}</p>
      <div className="flex flex-wrap gap-1.5">
        {skills.map((s) => (
          <Badge key={s} variant={variant}>
            {s}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-24 w-full" />
    </div>
  );
}
