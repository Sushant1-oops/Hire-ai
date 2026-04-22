export default function EmptyState({ icon = "◎", title, body }) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "56px 24px",
        color: "var(--text-muted)",
      }}
    >
      <div style={{ fontSize: 38, marginBottom: 12, opacity: 0.5 }}>{icon}</div>
      <div
        style={{
          fontSize: 15,
          fontWeight: 600,
          color: "var(--text-dim)",
          marginBottom: 6,
          fontFamily: "var(--font-display)",
        }}
      >
        {title}
      </div>
      {body && <div style={{ fontSize: 13.5 }}>{body}</div>}
    </div>
  );
}
