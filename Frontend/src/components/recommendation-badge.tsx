import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const TONES: Record<string, string> = {
  "Strong Hire": "border-transparent bg-success/15 text-success",
  Consider: "border-transparent bg-warning/25 text-foreground",
  "Weak Fit": "border-transparent bg-secondary text-secondary-foreground",
  "Not Recommended": "text-muted-foreground",
  Processing: "text-muted-foreground",
  "Failed to process": "border-transparent bg-destructive/10 text-destructive",
};

export function RecommendationBadge({
  value,
  className,
}: {
  value: string | undefined | null;
  className?: string;
}) {
  if (!value) return null;
  return (
    <Badge variant="outline" className={cn("whitespace-nowrap", TONES[value], className)}>
      {value}
    </Badge>
  );
}
