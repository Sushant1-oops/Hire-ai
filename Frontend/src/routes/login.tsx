import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useEffect } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { AuthLayout } from "@/components/auth-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";

export const Route = createFileRoute("/login")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Sign in — HireAI Semantic Hiring Assistant" },
      { name: "description", content: "Sign in to HireAI to search resumes semantically and rank candidates with AI." },
      { property: "og:title", content: "Sign in — HireAI" },
      { property: "og:description", content: "Access your AI semantic hiring workspace." },
    ],
  }),
  component: LoginPage,
});

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(6, "At least 6 characters"),
});

function LoginPage() {
  const { login, isAuthenticated, isReady } = useAuth();
  const navigate = useNavigate();
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  useEffect(() => {
    if (isReady && isAuthenticated) navigate({ to: "/dashboard", replace: true });
  }, [isReady, isAuthenticated, navigate]);

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      await login(values.email, values.password);
      toast.success("Welcome back");
      navigate({ to: "/dashboard", replace: true });
    } catch (error) {
      toast.error((error as Error).message);
    }
  });

  return (
    <AuthLayout title="Sign in" subtitle="Use your recruiter account to continue.">
      <form onSubmit={onSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">Work email</Label>
          <Input id="email" type="email" placeholder="you@company.com" {...form.register("email")} />
          <FieldError message={form.formState.errors.email?.message} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" {...form.register("password")} />
          <FieldError message={form.formState.errors.password?.message} />
        </div>
        <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting && <Loader2 className="size-4 animate-spin" />}
          Sign in
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          No account?{" "}
          <Link to="/register" className="font-medium text-primary hover:underline">
            Create one
          </Link>
        </p>
      </form>
    </AuthLayout>
  );
}

export function FieldError({ message }: { message?: string | undefined }) {
  if (!message) return null;
  return <p className="text-xs text-destructive">{message}</p>;
}
