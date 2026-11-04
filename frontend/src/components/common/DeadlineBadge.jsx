import React from "react";

const DAY_MS = 24 * 60 * 60 * 1000;

/** Days from today until the due date (negative once it has passed), or null. */
function daysUntil(dueDate, now = new Date()) {
    if (!dueDate) return null;
    const due = new Date(dueDate);
    if (Number.isNaN(due.getTime())) return null;
    return Math.ceil((due.getTime() - now.getTime()) / DAY_MS);
}

/** "Closed", "Closes in 12 days", "Open" or "No due date", colored by urgency. */
function DeadlineBadge({ dueDate }) {
    const days = daysUntil(dueDate);

    let label = "No due date";
    let colors = neutral;
    if (days !== null && days < 0) {
        label = "Closed";
        colors = closed;
    } else if (days !== null && days <= 30) {
        label = days === 0 ? "Closes today" : `Closes in ${days} day${days === 1 ? "" : "s"}`;
        colors = soon;
    } else if (days !== null) {
        label = "Open";
        colors = open;
    }

    return <span style={{ ...badgeStyle, ...colors }}>{label}</span>;
}

const badgeStyle = {
    display: "inline-block",
    padding: "3px 10px",
    borderRadius: "999px",
    fontSize: "12px",
    fontWeight: 700,
    whiteSpace: "nowrap",
};

const neutral = { backgroundColor: "#eef1f5", color: "#475569" };
const closed = { backgroundColor: "#f1f5f9", color: "#64748b" };
const soon = { backgroundColor: "#fff1e6", color: "#b54708" };
const open = { backgroundColor: "#e7f6ec", color: "#1a7f37" };

export default DeadlineBadge;
