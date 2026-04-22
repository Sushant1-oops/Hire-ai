export default function ScoreBar({ value = 0, label }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  const color =
    pct >= 70 ? "var(--emerald)" : pct >= 50 ? "var(--amber)" : "var(--rose)";

  return (
    <div>
      {label && (
        <div
          className="font-mono"
          style={{
            fontSize: 10,
            color: "var(--text-muted)",
            marginBottom: 5,
            textTransform: "uppercase",
            letterSpacing: "0.07em",
          }}
        >
          {label}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div className="score-track" style={{ flex: 1 }}>
          <div
            className="score-fill"
            style={{ width: `${pct}%`, background: color }}
          />
        </div>
        <span
          className="font-mono"
          style={{ fontSize: 11, color, minWidth: 34, textAlign: "right" }}
        >
          {pct}%
        </span>
      </div>
    </div>
  );
}
