export default function Label({ children, htmlFor }) {
  return (
    <label htmlFor={htmlFor} className="field-label">
      {children}
    </label>
  );
}
