import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  ssr: false,
  beforeLoad: () => {
    if (typeof window === "undefined") return;
    const authed = !!window.localStorage.getItem("hireai.access_token");
    throw redirect({ to: authed ? "/dashboard" : "/login" });
  },
  component: () => null,
});
