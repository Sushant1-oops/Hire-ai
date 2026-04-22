export default function Spinner({ size = 20, color = "var(--amber)" }) {
  return (
    <span
      className="spinner"
      style={{
        width: size,
        height: size,
        borderTopColor: color,
        flexShrink: 0,
      }}
    />
  );
}
