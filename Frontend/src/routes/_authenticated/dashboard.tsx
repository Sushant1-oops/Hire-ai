import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { FileText, Timer, Search as SearchIcon, TrendingUp } from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AppShell } from "@/components/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { dashboardStatsQuery } from "@/lib/queries";

export const Route = createFileRoute("/_authenticated/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — HireAI Hiring Analytics" },
      {
        name: "description",
        content: "Track resume volume, experience distribution and top candidate skills.",
      },
      { property: "og:title", content: "HireAI Dashboard" },
      { property: "og:description", content: "Hiring analytics across your candidate pool." },
    ],
  }),
  component: DashboardPage,
});

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

function DashboardPage() {
  const { data, isLoading, error } = useQuery(dashboardStatsQuery());

  const topSkills = data?.top_skills ?? [];
  const distribution = data?.experience_distribution ?? [];

  return (
    <AppShell title="Dashboard" description="Your candidate pool at a glance">
      {error && (
        <p className="mb-6 rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
          {(error as Error).message}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: "Total resumes", value: data?.total_resumes ?? 0, icon: FileText },
          {
            label: "Average experience",
            value: `${(data?.avg_experience ?? 0).toFixed(1)} yrs`,
            icon: Timer,
          },
          { label: "Tracked skills", value: topSkills.length, icon: TrendingUp },
          { label: "Recent searches", value: data?.recent_searches?.length ?? 0, icon: SearchIcon },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
          >
            <Card className="shadow-soft">
              <CardContent className="flex items-center justify-between pt-6">
                <div>
                  <p className="text-sm text-muted-foreground">{stat.label}</p>
                  {isLoading ? (
                    <Skeleton className="mt-2 h-7 w-20" />
                  ) : (
                    <p className="mt-1 text-2xl font-semibold tracking-tight">{stat.value}</p>
                  )}
                </div>
                <span className="flex size-10 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                  <stat.icon className="size-5" />
                </span>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card className="shadow-soft">
          <CardHeader>
            <CardTitle className="text-base">Experience distribution</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={distribution}
                    dataKey="count"
                    nameKey="range"
                    innerRadius={65}
                    outerRadius={100}
                    paddingAngle={3}
                  >
                    {distribution.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card className="shadow-soft">
          <CardHeader>
            <CardTitle className="text-base">Top skills</CardTitle>
          </CardHeader>
          <CardContent className="h-72">
            {isLoading ? (
              <Skeleton className="h-full w-full" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topSkills.slice(0, 8)}>
                  <XAxis dataKey="skill" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis tickLine={false} axisLine={false} fontSize={12} width={28} />
                  <Tooltip cursor={{ fill: "var(--muted)" }} />
                  <Bar dataKey="count" fill="var(--chart-1)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="mt-6 grid gap-4">
        <Card className="shadow-soft">
          <CardHeader>
            <CardTitle className="text-base">Recent searches</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading && <Skeleton className="h-32 w-full" />}
            {(data?.recent_searches ?? []).slice(0, 6).map((s, i) => (
              <motion.p
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="truncate rounded-lg bg-muted px-3 py-2 text-sm"
              >
                {s.query}
              </motion.p>
            ))}
            {!isLoading && !data?.recent_searches?.length && (
              <p className="text-sm text-muted-foreground">No searches yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
