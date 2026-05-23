import React from "react";

export default function EmptyState({
  icon = "•",
  title,
  hint,
  action,
}: {
  icon?: string;
  title: string;
  hint?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <div className="icon">{icon}</div>
      <div className="title">{title}</div>
      {hint && <div className="small">{hint}</div>}
      {action && <div style={{ marginTop: 10 }}>{action}</div>}
    </div>
  );
}
