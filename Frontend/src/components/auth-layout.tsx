import { motion } from "motion/react";
import { Sparkles, ShieldCheck, Zap, Users } from "lucide-react";
import type { ReactNode } from "react";

const POINTS = [
  { icon: Zap, title: "Semantic search", body: "Find the right candidate by meaning, not keywords." },
  { icon: Users, title: "Ranked shortlists", body: "Scored matches with strengths and gaps explained." },
  { icon: ShieldCheck, title: "AI hiring copilot", body: "Interview questions, emails and JDs in one click." },
];

export function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-brand-gradient p-12 text-primary-foreground lg:flex lg:flex-col lg:justify-between">
        <motion.div
          className="absolute -top-24 -right-16 size-96 rounded-full bg-white/10 blur-3xl"
          animate={{ scale: [1, 1.15, 1], opacity: [0.5, 0.8, 0.5] }}
          transition={{ duration: 9, repeat: Infinity }}
        />
        <motion.div
          className="absolute bottom-0 -left-20 size-80 rounded-full bg-white/10 blur-3xl"
          animate={{ scale: [1.1, 1, 1.1] }}
          transition={{ duration: 11, repeat: Infinity }}
        />
        <div className="relative flex items-center gap-2">
          <span className="flex size-9 items-center justify-center rounded-xl bg-white/15">
            <Sparkles className="size-5" />
          </span>
          <span className="text-lg font-semibold tracking-tight">HireAI</span>
        </div>
        <div className="relative space-y-8">
          <h2 className="max-w-md text-4xl leading-tight font-semibold tracking-tight">
            AI-powered hiring that reads between the lines.
          </h2>
          <div className="space-y-5">
            {POINTS.map((p, i) => (
              <motion.div
                key={p.title}
                initial={{ opacity: 0, x: -16 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 * i + 0.2 }}
                className="flex gap-3"
              >
                <p.icon className="mt-0.5 size-5 shrink-0 opacity-90" />
                <div>
                  <p className="font-medium">{p.title}</p>
                  <p className="text-sm text-primary-foreground/70">{p.body}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-primary-foreground/60">
          Trusted by hiring teams to screen thousands of resumes in seconds.
        </p>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-sm"
        >
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
          <div className="mt-8">{children}</div>
        </motion.div>
      </div>
    </div>
  );
}
