import { useEffect } from "react";

export default function Modal({ title, onClose, children, maxWidth = 700 }) {
  // Close on Escape key
  useEffect(() => {
    const handler = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div
      className="modal-overlay"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="modal-box" style={{ maxWidth }}>
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "20px 24px 16px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <h2
            className="font-display"
            style={{ fontSize: 17, fontWeight: 700 }}
          >
            {title}
          </h2>
          <button
            className="btn btn-ghost"
            onClick={onClose}
            style={{ padding: "4px 10px", fontSize: 18, lineHeight: 1 }}
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "20px 24px" }}>{children}</div>
      </div>
    </div>
  );
}
