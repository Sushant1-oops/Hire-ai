import { motion } from "motion/react";
import { cn } from "@/lib/utils";

export function toPercent(value: number | undefined) {
  if (value === undefined || Number.isNaN(value)) return 0;
  const pct = value <= 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(pct)));
}

export function ScoreRing({
  value,
  size = 72,
  label,
}: {
  value: number;
  size?: number;
  label?: string;
}) {
  const pct = toPercent(value);
  const stroke = 7;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          className="fill-none stroke-secondary"
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          strokeLinecap="round"
          className="fill-none stroke-primary"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference - (pct / 100) * circumference }}
          transition={{ duration: 0.9, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-sm font-semibold">{pct}%</span>
        {label && <span className="text-[10px] text-muted-foreground">{label}</span>}
      </div>
    </div>
  );
}

export function MetricBar({
  label,
  value,
  className,
}: {
  label: string;
  value: number;
  className?: string;
}) {
  const pct = toPercent(value);
  return (
    <div className={cn("space-y-1", className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{pct}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
        <motion.div
          className="h-full rounded-full bg-primary"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.7, ease: "easeOut" }}
        />
      </div>
    </div>
  );
}
