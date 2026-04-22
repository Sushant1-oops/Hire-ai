export default function SectionCard({ children, className = "", style = {}, hover = false }) {
  return (
    <div
      className={`card ${hover ? "card-glow" : ""} ${className}`}
      style={style}
    >
      {children}
    </div>
  );
}
