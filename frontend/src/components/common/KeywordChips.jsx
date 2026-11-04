import React from "react";

/**
 * Keywords or topics as small chips. The score, when given, is shown on hover
 * (the client's scores are kept but not emphasized).
 *
 * @param {{label: string, score?: number}[]} items
 */
function KeywordChips({ items }) {
    if (!items?.length) {
        return <p style={{ color: "var(--text-muted)" }}>Not available</p>;
    }

    return (
        <div style={wrapStyle}>
            {items.map((item, index) => (
                <span
                    key={`${item.label}-${index}`}
                    style={chipStyle}
                    title={item.score !== undefined && item.score !== null ? `Score: ${Number(item.score).toFixed(3)}` : undefined}
                >
                    {item.label}
                </span>
            ))}
        </div>
    );
}

const wrapStyle = {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
};

const chipStyle = {
    padding: "5px 10px",
    borderRadius: "999px",
    backgroundColor: "#eef4fa",
    color: "var(--auburn-navy)",
    fontSize: "13px",
    fontWeight: 500,
};

export default KeywordChips;
