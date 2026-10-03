import { Plus, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** "React, Node.js, Docker" -> three separate skills. */
export function splitSkillText(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Appends new skills, ignoring case-insensitive duplicates. */
export function mergeSkills(existing: string[], incoming: string[]): string[] {
  const next = [...existing];
  const seen = new Set(existing.map((s) => s.toLowerCase()));
  for (const skill of incoming) {
    if (!seen.has(skill.toLowerCase())) {
      seen.add(skill.toLowerCase());
      next.push(skill);
    }
  }
  return next;
}

/**
 * Chip input. The uncommitted draft lives in the PARENT so it can flush whatever is
 * still typed when the form is submitted (otherwise skills that are visibly in the
 * box are silently dropped from the request).
 */
export function SkillInput({
  label,
  skills,
  onChange,
  draft,
  onDraftChange,
  placeholder,
  hint,
}: {
  label: string;
  skills: string[];
  onChange: (next: string[]) => void;
  draft: string;
  onDraftChange: (next: string) => void;
  placeholder: string;
  hint?: string;
}) {
  const add = () => {
    const parsed = splitSkillText(draft);
    if (parsed.length) onChange(mergeSkills(skills, parsed));
    onDraftChange("");
  };
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className="flex gap-2">
        <Input
          value={draft}
          onChange={(e) => onDraftChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
        />
        <Button
          type="button"
          variant="secondary"
          size="icon"
          onClick={add}
          aria-label={`Add ${label}`}
        >
          <Plus className="size-4" />
        </Button>
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {!!skills.length && (
        <div className="flex flex-wrap gap-1.5">
          {skills.map((skill) => (
            <Badge key={skill} variant="secondary" className="gap-1">
              {skill}
              <button
                type="button"
                onClick={() => onChange(skills.filter((s) => s !== skill))}
                aria-label={`Remove ${skill}`}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
