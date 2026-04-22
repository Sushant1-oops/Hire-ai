const CONFIG = {
  "Strong Hire": { cls: "tag-emerald", icon: "▲" },
  Consider:      { cls: "tag-amber",   icon: "●" },
  Reject:        { cls: "tag-rose",    icon: "▼" },
};

export default function RecommendationBadge({ recommendation }) {
  const cfg = CONFIG[recommendation] ?? CONFIG["Consider"];
  return (
    <span className={`tag ${cfg.cls}`}>
      {cfg.icon} {recommendation}
    </span>
  );
}
